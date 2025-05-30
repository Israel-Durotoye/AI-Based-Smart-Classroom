import os
import torch
import torchaudio
from torch.utils.data import Dataset
import json
from tqdm import tqdm
from transformers import Wav2Vec2Processor
from datasets import load_dataset
import numpy as np

class GigaSpeechDataset(Dataset):
    def __init__(self, json_path, subset='XS', max_duration=10.0, sample_rate=16000):
        """
        Args:
            json_path: Path to GigaSpeech metadata JSON file
            subset: Which subset to use ('XS', 'S', 'M', 'L', 'XL')
            max_duration: Maximum audio duration in seconds
            sample_rate: Target sample rate
        """
        super().__init__()
        self.sample_rate = sample_rate
        self.max_duration = max_duration
        self.processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
        
        print(f"Loading GigaSpeech {subset} subset...")
        self.data = []
        
        # Load metadata
        with open(json_path, 'r') as f:
            metadata = json.load(f)
            
        # Filter by subset
        for audio_file in tqdm(metadata['audios']):
            if audio_file['subsets'][0] == subset:
                for segment in audio_file['segments']:
                    if float(segment['end_time']) - float(segment['begin_time']) <= max_duration:
                        self.data.append({
                            'audio_path': audio_file['path'],
                            'start': float(segment['begin_time']),
                            'end': float(segment['end_time']),
                            'text': segment['text_tn']
                        })

        print(f"Loaded {len(self.data)} segments from GigaSpeech {subset} subset")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Load audio
        waveform, sample_rate = torchaudio.load(item['audio_path'])
        
        # Extract segment
        start_frame = int(item['start'] * sample_rate)
        end_frame = int(item['end'] * sample_rate)
        waveform = waveform[:, start_frame:end_frame]
        
        # Resample if necessary
        if sample_rate != self.sample_rate:
            resampler = torchaudio.transforms.Resample(sample_rate, self.sample_rate)
            waveform = resampler(waveform)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Process audio
        inputs = self.processor(waveform.squeeze().numpy(), 
                              sampling_rate=self.sample_rate, 
                              return_tensors="pt",
                              padding=True)
        
        # Process text
        with self.processor.as_target_processor():
            labels = self.processor(item['text'], return_tensors="pt").input_ids
        
        return {
            'input_values': inputs.input_values.squeeze(),
            'labels': labels.squeeze()
        }

def download_gigaspeech(output_dir='gigaspeech_data', subset='xs'):
    """
    Downloads GigaSpeech dataset using HuggingFace datasets library
    
    Args:
        output_dir: Directory to save the dataset
        subset: Which subset to use ('xs', 's', 'm', 'l', 'xl')
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"Downloading GigaSpeech {subset} subset...")
    
    try:
        # Load dataset from HuggingFace
        dataset = load_dataset("speechcolab/gigaspeech", subset, use_auth_token=True)
        
        # Create metadata file
        metadata = {
            'audios': []
        }
        
        print("Processing dataset...")
        for split in dataset.keys():
            print(f"Processing {split} split...")
            for item in tqdm(dataset[split]):
                audio_info = {
                    'path': item['audio']['path'],
                    'subsets': [subset.upper()],
                    'segments': [{
                        'begin_time': item['begin_time'],
                        'end_time': item['end_time'],
                        'text_tn': item['text']
                    }]
                }
                metadata['audios'].append(audio_info)
        
        # Save metadata
        metadata_path = os.path.join(output_dir, 'GigaSpeech.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"Dataset downloaded and processed. Metadata saved to {metadata_path}")
        return True
        
    except Exception as e:
        print(f"Error downloading dataset: {str(e)}")
        print("Note: You need to:")
        print("1. Sign up at HuggingFace (https://huggingface.co)")
        print("2. Accept the terms at https://huggingface.co/datasets/speechcolab/gigaspeech")
        print("3. Get your access token from https://huggingface.co/settings/tokens")
        print("4. Set the token as an environment variable: export HUGGINGFACE_TOKEN=your_token")
        return False
