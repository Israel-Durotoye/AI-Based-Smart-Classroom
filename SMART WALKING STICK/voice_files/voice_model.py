from vosk import Model, KaldiRecognizer
import pyaudio
import pyttsx3
import json
import os
from datetime import datetime
import subprocess
import platform
import psutil
import requests
import random

class VoiceAssistant:
    def __init__(self):
        # Initialize TTS engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)  # speed
        self.engine.setProperty('volume', 1.0)  # volume
        
        # Get available voices and try to set a better quality one
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if "english" in voice.name.lower() and ("premium" in voice.name.lower() or "enhanced" in voice.name.lower()):
                self.engine.setProperty('voice', voice.id)
                break
        
        # Initialize Vosk model
        if not os.path.exists("vosk-model"):
            raise Exception("Vosk model not found! Please download and extract it first.")
        
        self.model = Model("vosk-model")
        self.recognizer = KaldiRecognizer(self.model, 16000)
        
        # Initialize microphone
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=16000,
                                input=True,
                                frames_per_buffer=8192)
        
        # Conversation context
        self.context = {
            "last_command": None,
            "conversation_history": [],
            "command_count": 0
        }
        
        # Natural language responses
        self.responses = {
            "greetings": [
                "Hello! How can I help you?",
                "Hi there! What can I do for you?",
                "Hey! I'm listening.",
                "Greetings! How may I assist you?"
            ],
            "acknowledgments": [
                "Okay, I'll do that.",
                "Sure thing!",
                "Got it!",
                "I'm on it!",
                "Consider it done."
            ],
            "confusion": [
                "I didn't quite catch that. Could you please repeat?",
                "Sorry, I'm not sure what you mean. Can you rephrase that?",
                "I'm having trouble understanding. Could you say that differently?",
                "Could you be more specific?"
            ],
            "farewells": [
                "Goodbye! Have a great day!",
                "See you later!",
                "Take care!",
                "Bye! Let me know if you need anything else."
            ],
            "system_status": [
                "Here's what I found about your system:",
                "Let me check your system information:",
                "Here are your system details:"
            ],
            "knowledge_intro": [
                "Here's an interesting fact:",
                "Did you know?",
                "Fun fact!",
                "Here's something fascinating:",
                "This might surprise you:"
            ],
            "category_intro": [
                "Here's something about {}:",
                "Let me tell you about {}:",
                "Speaking of {}, did you know:",
                "Here's a cool {} fact:"
            ]
        }

        # Knowledge base - consolidated fun facts
        self.fun_facts = [
            "A day on Venus is longer than its year.",
            "Octopuses have three hearts.",
            "Bananas are berries, but strawberries aren't.",
            "Sharks are older than trees.",
            "Wombat poop is cube-shaped.",
            "Water can boil and freeze at the same time.",
            "DNA in your body could stretch to Pluto and back 17 times.",
            "Lightning is five times hotter than the surface of the sun.",
            "Atoms are mostly empty space. If removed, humans fit in a sugar cube.",
            "Trees communicate underground via fungi networks.",
            "Neutron stars are so dense a spoonful weighs a billion tons.",
            "There are more stars than grains of sand on Earth.",
            "On Mars, sunsets appear blue.",
            "The moon is drifting away from Earth slowly.",
            "The first computer virus was called Brain.",
            "AI as a term was coined in 1956.",
            "Your brain can beat any supercomputer in raw operations.",
            "Zero isn't in Roman numerals.",
            "Palindrome words like 'madam' read the same both ways.",
            "The Mona Lisa has no eyebrows!",
            "Honey never spoils. Ancient Egyptian tombs had edible honey.",
            "Cows have best friends and get stressed when separated.",
            "The Great Wall of China is not visible from space.",
            "A hummingbird weighs less than a penny.",
            "The first oranges weren't orange - they were green.",
            "A blue whale's heart is the size of a small car.",
            "Penguins have knees inside their bodies.",
            "Your fingerprints are unique even among identical twins.",
            "The shortest war in history lasted 38 minutes.",
            "The average cloud weighs about 1.1 million pounds.",
            "A blue whale's tongue weighs as much as an elephant.",
            "Sloths are so slow that algae grows on their fur.",
            "An ostrich's eye is bigger than its brain.",
            "Butterflies taste with their feet.",
            "Dolphins give each other names and respond to them.",
            "The fingerprints of koalas are similar to human fingerprints.",
            "The longest recorded flight of a chicken is 13 seconds.",
            "Giraffes have the same number of neck vertebrae as humans.",
            "Kangaroos can't walk backward.",
            "Polar bears are left-handed.",
            "The heart of a shrimp is in its head.",
            "An elephant is the only mammal that can't jump.",
            "A rhinoceros horn is made of compacted hair.",
            "The only continent without native reptiles or snakes is Antarctica.",
            "A goldfish's memory lasts several months, not just 3 seconds.",
            "The Milky Way galaxy smells like raspberries and rum.",
            "Human teeth are just as strong as shark teeth.",
            "Sound travels 4.3 times faster in water than in air.",
            "The Earth's core is as hot as the surface of the sun.",
            "A bolt of lightning contains enough energy to toast 100,000 slices of bread.",
            "The first person convicted of speeding was going 8 mph.",
            "The inventor of the Frisbee was turned into a Frisbee after death.",
            "The shortest commercial flight in the world is 1.5 minutes long.",
            "The world's deepest postbox is 10 meters underwater.",
            "Nintendo was founded in 1889 as a playing card company.",
            "The average person spends 6 months of their lifetime waiting for red lights.",
            "The first oranges weren't orange - they were green.",
            "The average cumulus cloud weighs 1.1 million pounds.",
            "Pepsi once had the 6th largest military fleet in the world.",
            "Ancient Romans used crushed mouse brains as toothpaste.",
            "The moon has moonquakes.",
            "Bananas are naturally radioactive.",
            "A day on Pluto is 153 hours long.",
            "Astronauts grow taller in space.",
            "Venus spins backwards compared to other planets.",
            "The first email was sent in 1971.",
            "The most common password is '123456'.",
            "The first computer mouse was made of wood.",
            "The first webpage is still online.",
            "The QWERTY keyboard was designed to slow typing.",
            "The first text message said 'Merry Christmas'.",
            "The human body contains enough carbon to make 900 pencils.",
            "Your body produces enough heat in 30 minutes to boil a gallon of water.",
            "The human body generates enough pressure to shoot blood 30 feet.",
            "The average person walks the equivalent of three times around the world in a lifetime.",
            "The average person spends 2 weeks of their life kissing.",
            "Every time you lick a stamp, you consume 1/10 of a calorie.",
            "Humans share 50% of their DNA with bananas.",
            "The average person has over 1,460 dreams a year.",
            "The first person to reach the North Pole was a black man named Matthew Henson."
        ]

        # Knowledge intro phrases
        self.fact_intros = [
            "Here's an interesting fact:",
            "Did you know?",
            "Fun fact!",
            "Here's something fascinating:",
            "This might surprise you:",
            "Want to hear something cool?",
            "Check this out:",
            "Here's a mind-blowing fact:",
            "Prepare to be amazed:",
            "I bet you didn't know this:"
        ]
        
        # Last shared fact to avoid repetition
        self.last_fact = None
        
        # Add keyword mappings for intent detection
        self.keywords = {
            "joke": {
                "words": ["joke", "funny", "laugh", "humor"],
                "intent": "tell_joke",
                "confirmation": "Would you like me to tell you a joke?",
                "action": self.tell_joke
            },
            "fact": {
                "words": ["fact", "learn", "tell me something", "did you know"],
                "intent": "share_fact",
                "confirmation": "Would you like to hear an interesting fact?",
                "action": self.tell_fun_fact
            },
            "system": {
                "words": ["system", "computer", "status", "info"],
                "intent": "system_info",
                "confirmation": "Should I check your system information?",
                "action": lambda: self.get_system_info()
            }
        }

        # Add confirmation responses
        self.responses["confirmation"] = {
            "yes": ["yes", "yeah", "sure", "okay", "yep", "correct", "right", "please"],
            "no": ["no", "nope", "nah", "don't", "negative", "wrong"]
        }

        # Track confirmation state
        self.awaiting_confirmation = None

    def speak(self, text):
        """Convert text to speech with emotional markers"""
        print("Assistant:", text)
        # Add small pauses for natural speech
        text = text.replace(",", " ")
        text = text.replace(".", " ")
        self.engine.say(text)
        self.engine.runAndWait()

    def get_system_info(self):
        """Get detailed system information"""
        system = platform.system()
        if system == "Darwin":  # macOS
            os_version = f"macOS {platform.mac_ver()[0]}"
        else:
            os_version = platform.platform()

        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return (f"You're running {os_version}. "
                f"CPU usage is {cpu_percent}%. "
                f"Memory usage is {memory.percent}%. "
                f"Disk space used: {disk.percent}%")

    def execute_system_command(self, command):
        """Safely execute system commands"""
        safe_commands = {
            "check cpu": "top -l 1 | grep -E '^CPU'",
            "check memory": "vm_stat",
            "check disk": "df -h",
            "list files": "ls -la",
            "current directory": "pwd"
        }
        
        if command in safe_commands:
            try:
                result = subprocess.check_output(safe_commands[command], shell=True)
                return result.decode('utf-8')
            except Exception as e:
                return f"Error executing command: {e}"
        return "Sorry, that command is not allowed for security reasons."

    def understand_context(self, command):
        """Understand command context and maintain conversation flow"""
        self.context["command_count"] += 1
        self.context["conversation_history"].append(command)
        
        # Check for conversation flow
        if len(self.context["conversation_history"]) > 1:
            last_command = self.context["conversation_history"][-2]
            if "what" in last_command and "that" in command.lower():
                # User is referring to previous command
                return self.context["last_command"]
        
        self.context["last_command"] = command
        return command

    def get_random_fact(self, category=None):
        """Get a random fact, optionally from a specific category"""
        if category:
            if category in self.knowledge_base:
                facts = self.knowledge_base[category]
                fact = random.choice(facts)
            else:
                return None
        else:
            # Get a fact from any category
            category = random.choice(list(self.knowledge_base.keys()))
            facts = self.knowledge_base[category]
            fact = random.choice(facts)
            
        # Avoid repeating the last fact if possible
        if len(facts) > 1:
            while fact == self.last_fact:
                fact = random.choice(facts)
                
        self.last_fact = fact
        return fact, category

    def tell_joke(self):
        """Tell a random joke"""
        joke = random.choice(self.knowledge_base["jokes"])
        return joke, "jokes"

    def detect_keywords(self, command):
        """Detect keywords in the command and return the matching intent"""
        command = command.lower()
        for intent, data in self.keywords.items():
            if any(word in command for word in data["words"]):
                return data
        return None

    def check_confirmation(self, command):
        """Check if the command is a confirmation response"""
        command = command.lower()
        if any(word in command for word in self.responses["confirmation"]["yes"]):
            return True
        if any(word in command for word in self.responses["confirmation"]["no"]):
            return False
        return None

    def process_command(self, command):
        """Process voice commands with context awareness"""
        command = self.understand_context(command.lower())

        # Check if we're waiting for confirmation
        if self.awaiting_confirmation:
            confirmation = self.check_confirmation(command)
            if confirmation is not None:
                if confirmation:
                    # Execute the confirmed action
                    result = self.awaiting_confirmation["action"]()
                    if result:
                        fact, category = result
                        self.speak(fact)
                else:
                    self.speak("Okay, what else can I help you with?")
                self.awaiting_confirmation = None
                return True
            else:
                self.speak("I didn't understand. Please say yes or no.")
                return True

        # Detect keywords in the command
        intent = self.detect_keywords(command)
        if intent:
            # Ask for confirmation
            self.speak(intent["confirmation"])
            self.awaiting_confirmation = intent
            return True

        # Fun facts and knowledge
        if any(phrase in command for phrase in ["tell me a fact", "fun fact", "did you know", "tell me something"]):
            if "space" in command:
                fact, category = self.get_random_fact("space")
            elif "science" in command:
                fact, category = self.get_random_fact("science")
            elif "tech" in command or "technology" in command:
                fact, category = self.get_random_fact("tech")
            elif "math" in command:
                fact, category = self.get_random_fact("math")
            elif "art" in command:
                fact, category = self.get_random_fact("art")
            else:
                fact, category = self.get_random_fact()
                
            if fact:
                intro = random.choice(self.responses["knowledge_intro"])
                self.speak(f"{intro} {fact}")
            return True
            
        # Tell me about a specific topic
        elif "tell me about" in command:
            for category in self.knowledge_base.keys():
                if category in command:
                    fact, _ = self.get_random_fact(category)
                    if fact:
                        intro = random.choice(self.responses["category_intro"]).format(category)
                        self.speak(f"{intro} {fact}")
                        return True
        
        # System commands
        if "system" in command or "computer" in command:
            info = self.get_system_info()
            self.speak(random.choice(self.responses["system_status"]) + " " + info)
            
        # File operations
        elif "list files" in command or "show files" in command:
            self.speak("Here are the files in the current directory:")
            result = self.execute_system_command("list files")
            self.speak(result[:100] + "... and more")
            
        # Time and date
        elif "time" in command:
            current_time = datetime.now().strftime("%I:%M %p")
            self.speak(f"It's {current_time}")
            
        elif "date" in command or "day" in command:
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            self.speak(f"Today is {current_date}")
            
        # Help and capabilities
        elif "what can you do" in command or "help" in command:
            capabilities = (
                "I can help you with: "
                "checking system information, "
                "managing files, "
                "telling time and date, "
                "sharing interesting facts about science, space, technology, and more, "
                "and executing basic system commands. "
                "Try saying 'tell me a fact' or 'tell me about space'!"
            )
            self.speak(capabilities)
            
        # Exit commands
        elif any(word in command for word in ["exit", "quit", "stop", "goodbye", "bye"]):
            self.speak(random.choice(self.responses["farewells"]))
            return False
            
        # Unknown command
        else:
            self.speak(random.choice(self.responses["confusion"]))
            
        return True

    def run(self):
        """Main loop for voice assistant"""
        self.stream.start_stream()
        self.speak("Hello! I'm your voice assistant. How can I help you today?")
        
        try:
            while True:
                try:
                    data = self.stream.read(4096, exception_on_overflow=False)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        command = result.get("text", "").strip()
                        
                        if command:
                            print("You said:", command)
                            if not self.process_command(command):
                                break
                except Exception as e:
                    print(f"Error processing audio: {e}")
                    continue
                    
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    try:
        assistant = VoiceAssistant()
        assistant.run()
    except Exception as e:
        print(f"Error: {e}")
        print("Please make sure you have all required dependencies installed.")
