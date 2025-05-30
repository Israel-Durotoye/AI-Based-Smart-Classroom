import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    GPT2LMHeadModel,
    GPT2Tokenizer,
    AdamW,
    get_linear_schedule_with_warmup,
    Trainer,
    TrainingArguments
)
import json
import numpy as np
import os
from datetime import datetime
from test_dht11 import DHT11Sensor

class ConversationDataset(Dataset):
    def __init__(self, tokenizer, conversations, max_length=128):
        self.tokenizer = tokenizer
        self.conversations = conversations
        self.max_length = max_length
        
    def __len__(self):
        return len(self.conversations)
        
    def __getitem__(self, idx):
        conversation = self.conversations[idx]
        input_text = conversation['input']
        response_text = conversation['response']
        
        # Combine input and response for training
        combined_text = f"{input_text} [SEP] {response_text}"
        
        # Tokenize and format for GPT2
        encodings = self.tokenizer(
            combined_text,
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors='pt'
        )
        
        return {
            'input_ids': encodings['input_ids'].squeeze(),
            'attention_mask': encodings['attention_mask'].squeeze(),
            'labels': encodings['input_ids'].squeeze()
        }

class VoiceChatModel:
    def __init__(self, model_path=None):
        """Initialize the voice chat model.
        
        Args:
            model_path: Path to saved model, or None to use pretrained
        """
        # Initialize tokenizer and model
        self.tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
        if model_path and os.path.exists(model_path):
            self.model = GPT2LMHeadModel.from_pretrained(model_path)
            print(f"Loaded model from {model_path}")
        else:
            self.model = GPT2LMHeadModel.from_pretrained('gpt2')
            print("Using pretrained GPT2 model")
            
        # Initialize sensors
        try:
            self.dht11 = DHT11Sensor()
            print("Temperature sensor initialized")
        except:
            self.dht11 = None
            print("Temperature sensor not available")
            
        # Add special tokens
        special_tokens = {
            'additional_special_tokens': [
                '[USER]', '[BOT]', '[SEP]',
                '[WEATHER]', '[LOCATION]', '[TIME]', '[NAME]'
            ]
        }
        self.tokenizer.add_special_tokens(special_tokens)
        self.model.resize_token_embeddings(len(self.tokenizer))
        
        # Context management
        self.context = {
            'user_name': None,
            'last_interaction': None,
            'conversation_history': [],
            'topic': None
        }
        
        # Load personality and responses
        self._load_personality()
        
    def _load_personality(self):
        """Load personality traits and predefined responses."""
        self.personality = {
            'name': 'Assistant',
            'traits': ['helpful', 'friendly', 'knowledgeable'],
            'responses': {
                'greetings': [
                    "Hello! How can I help you today?",
                    "Hi there! What's on your mind?",
                    "Greetings! How may I assist you?"
                ],
                'farewells': [
                    "Goodbye! Have a great day!",
                    "See you later! Take care!",
                    "Bye for now! Stay safe!"
                ],
                'name_intro': [
                    "Nice to meet you, {}! I'm your AI assistant.",
                    "Hello {}! I'm delighted to make your acquaintance.",
                    "Great to meet you, {}! Looking forward to our conversation."
                ],
                'weather_responses': {
                    'cold': [
                        "It's quite chilly! You might want to wear something warm.",
                        "The temperature is on the lower side today.",
                        "Bundle up! It's cold out there."
                    ],
                    'comfortable': [
                        "The temperature is just right for a walk!",
                        "Weather conditions are quite pleasant right now.",
                        "It's a comfortable day temperature-wise."
                    ],
                    'warm': [
                        "It's pretty warm today. Stay hydrated!",
                        "The temperature is on the warmer side.",
                        "Make sure to stay cool in this warm weather."
                    ]
                },
                'fallbacks': [
                    "I'm not quite sure about that. Could you rephrase?",
                    "I'm still learning about that topic.",
                    "That's an interesting question! Let me think about it."
                ],
                'confirmations': [
                    "I understand! Let me help you with that.",
                    "Got it! Here's what I know.",
                    "Sure thing! Here's the information you need."
                ]
            }
        }
        
    def _get_weather_response(self):
        """Get weather information and format response."""
        if not self.dht11:
            return "I'm sorry, but my temperature sensor isn't available right now."
            
        temp, humidity = self.dht11.read_sensor()
        if temp is None or humidity is None:
            return "I'm having trouble reading the weather conditions."
            
        # Determine weather category
        if temp < 18:
            category = 'cold'
        elif temp < 25:
            category = 'comfortable'
        else:
            category = 'warm'
            
        # Get random response for category
        response = np.random.choice(self.personality['responses']['weather_responses'][category])
        
        # Add specific temperature and humidity
        detail = f" The temperature is {temp:.1f}°C with {humidity:.1f}% humidity."
        
        return response + detail
        
    def train(self, training_data, epochs=3, batch_size=4, learning_rate=5e-5):
        """Train the model on custom data."""
        # Create dataset
        dataset = ConversationDataset(self.tokenizer, training_data)
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir="./results",
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            learning_rate=learning_rate,
            warmup_steps=100,
            logging_dir='./logs',
            logging_steps=10,
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
        )
        
        # Train model
        trainer.train()
        
    def save_model(self, path):
        """Save the model and tokenizer."""
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        print(f"Model saved to {path}")
        
    def _preprocess_input(self, user_input):
        """Preprocess user input for intent recognition."""
        user_input = user_input.lower().strip()
        
        # Check for specific intents
        intents = {
            'weather': ['weather', 'temperature', 'humidity', 'hot', 'cold'],
            'greeting': ['hello', 'hi', 'hey', 'greetings'],
            'farewell': ['bye', 'goodbye', 'see you', 'farewell'],
            'name': ['my name is', 'call me', 'i am'],
            'gratitude': ['thank', 'thanks'],
            'help': ['help', 'what can you do', 'abilities']
        }
        
        for intent, keywords in intents.items():
            if any(keyword in user_input for keyword in keywords):
                return intent
                
        return 'general'
        
    def generate_response(self, user_input, max_length=100):
        """Generate a response to user input."""
        # Update context
        self.context['last_interaction'] = datetime.now()
        self.context['conversation_history'].append(('user', user_input))
        
        # Preprocess input
        intent = self._preprocess_input(user_input)
        
        # Handle specific intents
        if intent == 'weather':
            response = self._get_weather_response()
        elif intent == 'greeting':
            response = np.random.choice(self.personality['responses']['greetings'])
            if self.context['user_name']:
                response = response.replace('!', f", {self.context['user_name']}!")
        elif intent == 'farewell':
            response = np.random.choice(self.personality['responses']['farewells'])
        elif intent == 'name':
            name = [word for word in user_input.split() if word not in ['my', 'name', 'is', 'call', 'me', 'i', 'am']][-1]
            self.context['user_name'] = name.capitalize()
            response = np.random.choice(self.personality['responses']['name_intro']).format(self.context['user_name'])
        elif intent == 'gratitude':
            response = "You're welcome! I'm happy to help!"
        elif intent == 'help':
            response = ("I can help you with weather information, remember your name, "
                      "and have friendly conversations. Just ask me anything!")
        else:
            # Use model for general conversation
            prompt = f"[USER] {user_input} [BOT]"
            inputs = self.tokenizer(prompt, return_tensors='pt', padding=True)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs['input_ids'],
                    max_length=max_length,
                    num_return_sequences=1,
                    pad_token_id=self.tokenizer.eos_token_id,
                    do_sample=True,
                    top_k=50,
                    top_p=0.95,
                    temperature=0.7
                )
                
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.replace(prompt, "").strip()
            
            # Fallback if response is too short or empty
            if len(response) < 5:
                response = np.random.choice(self.personality['responses']['fallbacks'])
        
        # Update conversation history
        self.context['conversation_history'].append(('assistant', response))
        return response

def create_training_data():
    """Create a custom training dataset."""
    return [
        {
            "input": "What's the weather like today?",
            "response": "Let me check the temperature and humidity sensors for you."
        },
        {
            "input": "My name is John",
            "response": "Nice to meet you, John! I'm your AI assistant."
        },
        {
            "input": "Hello",
            "response": "Hi there! How can I help you today?"
        },
        {
            "input": "What can you do?",
            "response": "I can help you with weather information, navigation, detecting obstacles, and having friendly conversations!"
        },
        {
            "input": "How are you?",
            "response": "I'm functioning well and ready to assist you! How are you today?"
        },
        {
            "input": "Tell me a joke",
            "response": "Why don't AI assistants tell jokes? Because we're too busy being helpful! Just kidding, I'm here to brighten your day."
        },
        {
            "input": "Is it hot outside?",
            "response": "Let me check the temperature sensor for you and give you an accurate reading."
        }
    ]

def main():
    # Initialize model
    model = VoiceChatModel()
    
    # Create and process training data
    print("Loading training data...")
    training_data = create_training_data()
    
    # Train model
    print("Training model...")
    model.train(training_data, epochs=3)
    
    # Save model
    model.save_model('voice_chat_model')
    
    # Interactive testing
    print("\nEntering interactive mode (type 'quit' to exit)")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
            
        response = model.generate_response(user_input)
        print(f"Assistant: {response}")

if __name__ == "__main__":
    main()