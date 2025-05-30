import torch
import torch.nn as nn
import torchaudio
import torchaudio.transforms as T
from torch.utils.data import Dataset, DataLoader
from typing import List, Tuple
import os

# Constants
SAMPLE_RATE = 16000
N_FFT = 400
N_MELS = 64
WIN_LENGTH = 400
HOP_LENGTH = 160

class AudioPreprocessor:
    def __init__(self):
        self.mel_spectrogram = T.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=N_FFT,
            win_length=WIN_LENGTH,
            hop_length=HOP_LENGTH,
            n_mels=N_MELS
        )
        self.amplitude_to_db = T.AmplitudeToDB()
    
    def __call__(self, waveform: torch.Tensor) -> torch.Tensor:
        mel_spec = self.mel_spectrogram(waveform)
        mel_db = self.amplitude_to_db(mel_spec)
        return mel_db

class SpeechRecognitionModel(nn.Module):
    def __init__(self, n_mels: int = N_MELS, n_classes: int = 10):
        super().__init__()
        
        # CNN layers
        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.25)
        
        # Calculate the size of flattened features
        self.fc_input_dim = 64 * (n_mels // 4) * 62  # Assuming typical input length
        
        # Fully connected layers
        self.fc1 = nn.Linear(self.fc_input_dim, 512)
        self.fc2 = nn.Linear(512, n_classes)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Add channel dimension if not present
        if x.dim() == 3:
            x = x.unsqueeze(1)
            
        # CNN layers
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.dropout(x)
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # Fully connected layers
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x

class AudioDataset(Dataset):
    def __init__(self, root_dir: str, transform=None):
        self.root_dir = root_dir
        self.transform = transform if transform else AudioPreprocessor()
        self.samples = []
        self.labels = []
        self.label_to_idx = {}
        self.idx_to_label = {}
        
        # Load dataset
        self._load_dataset()
    
    def _load_dataset(self):
        class_idx = 0
        for class_name in os.listdir(self.root_dir):
            class_path = os.path.join(self.root_dir, class_name)
            if os.path.isdir(class_path):
                self.label_to_idx[class_name] = class_idx
                self.idx_to_label[class_idx] = class_name
                
                for audio_file in os.listdir(class_path):
                    if audio_file.endswith('.wav'):
                        self.samples.append(os.path.join(class_path, audio_file))
                        self.labels.append(class_idx)
                
                class_idx += 1
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        audio_path = self.samples[idx]
        label = self.labels[idx]
        
        # Load audio
        waveform, sample_rate = torchaudio.load(audio_path)
        
        # Resample if necessary
        if sample_rate != SAMPLE_RATE:
            resampler = T.Resample(sample_rate, SAMPLE_RATE)
            waveform = resampler(waveform)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Apply transform
        if self.transform:
            waveform = self.transform(waveform)
        
        return waveform, label

def create_example_dataset():
    """Create example dataset structure with sample audio files."""
    dataset_path = "audio_data"
    os.makedirs(dataset_path, exist_ok=True)
    
    # Create class directories
    commands = ["left", "right", "forward", "backward", "stop"]
    for cmd in commands:
        os.makedirs(os.path.join(dataset_path, cmd), exist_ok=True)
    
    print(f"Created example dataset structure in {dataset_path}")
    print("Please add .wav audio files for each command in their respective folders:")
