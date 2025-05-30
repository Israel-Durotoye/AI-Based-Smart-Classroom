import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from datetime import datetime
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
from gigaspeech_dataset import GigaSpeechDataset, download_gigaspeech
import torch.nn.functional as F
from jiwer import wer
from typing import Dict, List
from tqdm.auto import tqdm

def collate_fn(batch):
    """Custom collate function for padding sequences in a batch"""
    input_values = [item['input_values'] for item in batch]
    labels = [item['labels'] for item in batch]
    
    # Pad input values
    input_lengths = torch.LongTensor([len(x) for x in input_values])
    input_values_padded = torch.nn.utils.rnn.pad_sequence(input_values, batch_first=True)
    
    # Pad labels
    labels_padded = torch.nn.utils.rnn.pad_sequence(labels, batch_first=True)
    
    return {
        'input_values': input_values_padded,
        'attention_mask': input_lengths,
        'labels': labels_padded
    }

def compute_metrics(pred_str: List[str], label_str: List[str]) -> Dict[str, float]:
    """
    Compute Word Error Rate and Character Error Rate
    Args:
        pred_str: List of predicted transcriptions
        label_str: List of ground truth transcriptions
    Returns:
        Dictionary containing WER (Word Error Rate)
    """
    # Word Error Rate
    wer_metric = wer(label_str, pred_str)
    
    return {
        "wer": wer_metric
    }

# Initialize the processor globally
processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")

def train_model(data_dir="gigaspeech_data", epochs=30, batch_size=16, learning_rate=1e-4):
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Create dataset and split into train/val
    full_dataset = GigaSpeechDataset(
        os.path.join(data_dir, "GigaSpeech.json"),
        subset='XS',  # Using the smallest subset for faster training
        max_duration=10.0
    )
    
    # Split dataset into train and validation
    train_size = int(0.9 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size]
    )
    
    train_loader = DataLoader(
        train_dataset, 
        batch_size=batch_size, 
        shuffle=True,
        collate_fn=collate_fn
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_fn
    )

    # Initialize model
    model = Wav2Vec2ForCTC.from_pretrained(
        "facebook/wav2vec2-base-960h",
        ctc_loss_reduction="mean",
        pad_token_id=processor.tokenizer.pad_token_id,
    )
    model = model.to(device)

    # Define optimizer and scheduler
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate)
    total_steps = len(train_loader) * epochs
    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=learning_rate,
        total_steps=total_steps,
        pct_start=0.1
    )

    # Create save directory if it doesn't exist
    os.makedirs('trained_models', exist_ok=True)
    save_dir = os.path.join('trained_models', datetime.now().strftime('%Y%m%d_%H%M%S'))
    os.makedirs(save_dir, exist_ok=True)

    print("Starting training...")
    best_val_loss = float('inf')
    best_wer = float('inf')  # Word Error Rate
    patience = 5
    patience_counter = 0
    
    # Training loop
    for epoch in range(epochs):
        # Training phase
        model.train()
        total_train_loss = 0
        
        for batch_idx, batch in enumerate(train_loader):
            # Move batch to device
            input_values = batch['input_values'].to(device)
            labels = batch['labels'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            
            # Zero the parameter gradients
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(
                input_values=input_values,
                attention_mask=attention_mask,
                labels=labels
            )
            
            loss = outputs.loss
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            # Optimization step
            optimizer.step()
            scheduler.step()
            
            # Statistics
            total_train_loss += loss.item()
            
            if batch_idx % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs}, Batch {batch_idx}, Loss: {loss.item():.4f}, LR: {scheduler.get_last_lr()[0]:.6f}")
        
        avg_train_loss = total_train_loss / len(train_loader)
        
        # Validation phase
        model.eval()
        total_val_loss = 0
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in val_loader:
                input_values = batch['input_values'].to(device)
                labels = batch['labels'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                
                outputs = model(
                    input_values=input_values,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                total_val_loss += loss.item()
                
                # Get predictions
                logits = outputs.logits
                pred_ids = torch.argmax(logits, dim=-1)
                
                # Convert ids to text
                pred_str = processor.batch_decode(pred_ids)
                label_str = processor.batch_decode(labels, group_tokens=False)
                
                all_preds.extend(pred_str)
                all_labels.extend(label_str)
        
        avg_val_loss = total_val_loss / len(val_loader)
        
        # Calculate Word Error Rate
        current_wer = wer(all_labels, all_preds)
        
        # Print epoch statistics
        print(f"\nEpoch {epoch+1}/{epochs} Summary:")
        print(f"Average Training Loss: {avg_train_loss:.4f}")
        print(f"Average Validation Loss: {avg_val_loss:.4f}")
        print(f"Word Error Rate: {current_wer:.4f}")
        
        # Save checkpoint
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict(),
            'train_loss': avg_train_loss,
            'val_loss': avg_val_loss,
            'wer': current_wer,
        }
        
        # Save latest checkpoint
        latest_path = os.path.join(save_dir, 'latest_checkpoint.pt')
        torch.save(checkpoint, latest_path)
        
        # Save best model based on validation loss
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_path = os.path.join(save_dir, 'best_model.pt')
            torch.save(checkpoint, best_path)
            print(f"New best model saved with validation loss: {best_val_loss:.4f}")
            patience_counter = 0
        else:
            patience_counter += 1
            
        # Early stopping
        if patience_counter >= patience:
            print(f"\nEarly stopping triggered after {patience} epochs without improvement")
            break
            
    print(f"\nTraining completed. Model checkpoints saved in: {save_dir}")

    # Create optimized version for Raspberry Pi
    print("\nCreating optimized version for Raspberry Pi...")
    model.eval()
    
    # Quantize the model
    quantized_model = torch.quantization.quantize_dynamic(
        model, {nn.Linear}, dtype=torch.qint8
    )
    
    # Save quantized model
    pi_save_path = os.path.join(save_dir, 'voice_assistant_model_quantized.pt')
    torch.save({
        'model_state_dict': quantized_model.state_dict(),
        'processor_config': processor.save_pretrained(save_dir),
        'val_loss': best_val_loss,
        'wer': current_wer,
    }, pi_save_path)
    print(f"Optimized model saved to: {pi_save_path}")

if __name__ == "__main__":
    # Download and set up GigaSpeech dataset
    download_gigaspeech()
    
    print("\nMake sure you have downloaded the GigaSpeech dataset and placed it in the gigaspeech_data directory.")
    print("The dataset should include:")
    print("- GigaSpeech.json (metadata file)")
    print("- wav/ directory (containing audio files)")
    print("\nAfter setting up the dataset, press Enter to start training...")
    input()
    
    train_model()