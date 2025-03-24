from aac_system import AACSystem
from output_postprocessing import (
    OutputChannelManager, 
    OutputConfig, 
    OutputMode
)
import json
from typing import Dict
import sys
import pyttsx3

class AACRunner:
    """Runner class to handle AAC system interaction"""
    
    def __init__(self):
        """Initialize the AAC system and output manager"""
        print("\n🚀 Initializing AAC System...")
        
        try:
            # Initialize AAC system
            self.aac = AACSystem()
            
            # Initialize output manager
            output_config = OutputConfig(
                mode=OutputMode.BOTH,
                speech_enabled=True,
                text_format="detailed"
            )
            self.output_manager = OutputChannelManager(
                config=output_config,
                speech_engine=self.aac.tts_engine
            )
            
            print("✅ System initialized successfully!")
            
        except Exception as e:
            print(f"❌ Error initializing system: {str(e)}")
            sys.exit(1)

    def get_input_type(self) -> str:
        """Prompt user for input type selection"""
        while True:
            print("\n📝 Choose input type:")
            print("1. Text input")
            print("2. Speech input")
            print("3. Configure output")
            print("q. Quit")
            
            choice = input("\nEnter your choice (1/2/3/q): ").lower()
            
            if choice == 'q':
                sys.exit(0)
            elif choice == '1':
                return "text"
            elif choice == '2':
                return "speech"
            elif choice == '3':
                self.configure_output()
                continue
            else:
                print("❌ Invalid choice. Please try again.")

    def configure_output(self) -> None:
        """Configure output settings"""
        print("\n⚙️ Output Configuration:")
        print("1. Text only")
        print("2. Speech only")
        print("3. Both text and speech")
        print("4. Custom plugin")
        
        choice = input("\nSelect output mode (1-4): ")
        
        mode_map = {
            "1": OutputMode.TEXT,
            "2": OutputMode.SPEECH,
            "3": OutputMode.BOTH,
            "4": OutputMode.CUSTOM_PLUGIN
        }
        
        if choice in mode_map:
            self.output_manager.update_config(mode=mode_map[choice])
            print(f"✅ Output mode updated to: {mode_map[choice].value}")
        else:
            print("❌ Invalid choice")

    def process_and_output(self, result: Dict) -> None:
        """Process results and output through configured channels"""
        output_result = self.output_manager.process_output(result)
        
        if output_result["status"] == "error":
            print(f"\n❌ Error: {output_result['message']}")

    def get_input_parameters(self, input_type: str) -> Dict:
        """Get additional parameters based on input type"""
        params = {"input_type": input_type}
        
        if input_type == "text":
            text = input("\n🔤 Enter your message: ")
            params["text"] = text
        else:  # speech
            print("\n🎤 Speech input configuration:")
            duration = input("Enter recording duration in seconds (default: 5): ")
            params["duration"] = int(duration) if duration.isdigit() else 5
            
        return params

    def run(self) -> None:
        """Main run loop"""
        print("\n👋 Welcome to the AAC System!")
        print(f"🔊 Current output mode: {self.output_manager.config.mode.value}")
        
        while True:
            try:
                # Get input type
                input_type = self.get_input_type()
                
                # Get input parameters
                params = self.get_input_parameters(input_type)
                
                # Process input
                print("\n⚙️ Processing input...")
                result = self.aac.process_user_input(**params)
                
                # Handle output
                self.process_and_output(result)
                
                # Ask to continue
                if input("\n🔄 Process another input? (y/n): ").lower() != 'y':
                    break
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                if input("\n🔄 Continue? (y/n): ").lower() != 'y':
                    break

if __name__ == "__main__":
    runner = AACRunner()
    runner.run() 