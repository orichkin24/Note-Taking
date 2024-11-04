import sys
import whisper
import pyaudio
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QTextEdit, QLabel, QComboBox, QSpinBox)
from PyQt5.QtCore import QThread, pyqtSignal
import queue
import time

class TranscriptionThread(QThread):
    transcription_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.model = whisper.load_model("base")
        self.p = pyaudio.PyAudio()
        self.selected_device_index = None
        self.audio_queue = queue.Queue()
        self.CHUNK_SIZE = 1024 * 32  # Larger chunk size for better processing
        self.SAMPLE_RATE = 16000
        self.CHANNELS = 1
        self.SILENCE_THRESHOLD = 0.005
        self.MIN_PHRASE_LENGTH = 10  # Minimum length for a phrase to be considered valid
        self.buffer_size_seconds = 10  # Default buffer size in seconds
        
    def get_available_devices(self):
        devices = []
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:  # Only include input devices
                name = dev['name']
                if 'CABLE Output' in name:
                    name = f"{name} (Virtual Cable)"
                else:
                    name = f"{name} (Microphone)"
                devices.append((name, i))
        return devices

    def set_device(self, device_index):
        self.selected_device_index = device_index

    def set_buffer_size(self, seconds):
        self.buffer_size_seconds = max(5, min(30, seconds))  # Limit between 5 and 30 seconds

    def audio_callback(self, in_data, frame_count, time_info, status):
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def is_silence(self, audio_data, threshold_multiplier=1.0):
        return np.max(np.abs(audio_data)) < (self.SILENCE_THRESHOLD * threshold_multiplier)

    def find_speech_boundaries(self, audio_data):
        """Find the boundaries of speech in the audio data"""
        window_size = 1024
        energy = np.array([
            np.mean(np.abs(audio_data[i:i+window_size]))
            for i in range(0, len(audio_data)-window_size, window_size)
        ])
        
        threshold = np.mean(energy) * 0.5
        speech_regions = energy > threshold
        
        if not any(speech_regions):
            return 0, len(audio_data)
            
        start = np.where(speech_regions)[0][0] * window_size
        end = (np.where(speech_regions)[0][-1] + 1) * window_size
        
        return max(0, start), min(len(audio_data), end)

    def run(self):
        if self.selected_device_index is None:
            self.error_signal.emit("No audio input device selected.")
            return

        try:
            stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.CHUNK_SIZE,
                input_device_index=self.selected_device_index,
                stream_callback=self.audio_callback
            )
            
            stream.start_stream()
            self.running = True
            
            audio_buffer = np.array([], dtype=np.float32)
            MIN_SAMPLES = int(self.SAMPLE_RATE * self.buffer_size_seconds)
            silence_duration = 0
            last_transcription = ""
            
            while self.running:
                # Collect audio data from queue
                while not self.audio_queue.empty():
                    data = self.audio_queue.get()
                    audio_chunk = np.frombuffer(data, dtype=np.float32)
                    audio_buffer = np.concatenate([audio_buffer, audio_chunk])
                
                # Process when we have enough data
                if len(audio_buffer) >= MIN_SAMPLES:
                    # Find speech boundaries in the buffer
                    start, end = self.find_speech_boundaries(audio_buffer[:MIN_SAMPLES])
                    
                    if end - start > self.SAMPLE_RATE:  # At least 1 second of speech
                        # Extract speech segment
                        speech_segment = audio_buffer[start:end]
                        
                        # Normalize audio
                        max_val = np.max(np.abs(speech_segment))
                        if max_val > 0:
                            speech_segment = speech_segment / max_val
                        
                        # Add padding for better sentence detection
                        padded_audio = np.pad(speech_segment, (0, self.SAMPLE_RATE), mode='constant')
                        
                        # Transcribe
                        result = self.model.transcribe(padded_audio, language='en', fp16=False)
                        transcript = result['text'].strip()
                        
                        # Only emit if we have meaningful text
                        if transcript and len(transcript) > self.MIN_PHRASE_LENGTH:
                            # Avoid duplicate transcriptions
                            if transcript.lower() not in last_transcription.lower():
                                self.transcription_signal.emit(transcript)
                                last_transcription = transcript
                    
                    # Keep a portion of the buffer for context
                    audio_buffer = audio_buffer[MIN_SAMPLES - self.SAMPLE_RATE:]
                
                time.sleep(0.1)
                
        except Exception as e:
            self.error_signal.emit(f"Error during transcription: {str(e)}")
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            self.audio_queue.queue.clear()

    def stop(self):
        self.running = False

class TranscriptionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meeting Transcription")
        self.setGeometry(100, 100, 800, 600)
        
        # Initialize transcription thread first
        self.transcription_thread = TranscriptionThread()
        self.transcription_thread.transcription_signal.connect(self.update_transcription)
        self.transcription_thread.error_signal.connect(self.show_error)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create device selection dropdown
        self.device_label = QLabel("Select Input Device:")
        layout.addWidget(self.device_label)
        
        self.device_combo = QComboBox()
        layout.addWidget(self.device_combo)
        
        # Create buffer size control
        buffer_layout = QVBoxLayout()
        self.buffer_label = QLabel("Buffer Size (seconds):")
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(5, 30)
        self.buffer_spin.setValue(10)
        self.buffer_spin.valueChanged.connect(self.on_buffer_size_changed)
        buffer_layout.addWidget(self.buffer_label)
        buffer_layout.addWidget(self.buffer_spin)
        layout.addLayout(buffer_layout)
        
        # Populate device list after creating combo box
        self.populate_device_list()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        
        # Create status label
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)
        
        # Create clear button
        self.clear_button = QPushButton("Clear Text")
        self.clear_button.clicked.connect(self.clear_text)
        layout.addWidget(self.clear_button)
        
        # Create start/stop button
        self.toggle_button = QPushButton("Start Transcription")
        self.toggle_button.clicked.connect(self.toggle_transcription)
        layout.addWidget(self.toggle_button)
        
        # Create text display area
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.text_display)
        
        self.is_transcribing = False

    def on_buffer_size_changed(self, value):
        self.transcription_thread.set_buffer_size(value)
        self.status_label.setText(f"Status: Buffer size set to {value} seconds")

    def clear_text(self):
        self.text_display.clear()

    def populate_device_list(self):
        self.device_combo.clear()
        devices = self.transcription_thread.get_available_devices()
        for name, _ in devices:
            self.device_combo.addItem(name)
        
        # Try to select Virtual Cable by default if available
        for i in range(self.device_combo.count()):
            if "Virtual Cable" in self.device_combo.itemText(i):
                self.device_combo.setCurrentIndex(i)
                break

    def on_device_changed(self, index):
        devices = self.transcription_thread.get_available_devices()
        if index >= 0 and index < len(devices):
            _, device_index = devices[index]
            self.transcription_thread.set_device(device_index)
            self.status_label.setText(f"Status: Ready - Using {self.device_combo.currentText()}")

    def toggle_transcription(self):
        if not self.is_transcribing:
            self.start_transcription()
        else:
            self.stop_transcription()

    def start_transcription(self):
        if self.device_combo.currentIndex() == -1:
            self.show_error("Please select an input device")
            return
            
        self.is_transcribing = True
        self.toggle_button.setText("Stop Transcription")
        self.status_label.setText(f"Status: Transcribing using {self.device_combo.currentText()}...")
        self.device_combo.setEnabled(False)
        self.buffer_spin.setEnabled(False)
        self.transcription_thread.start()

    def stop_transcription(self):
        self.is_transcribing = False
        self.toggle_button.setText("Start Transcription")
        self.status_label.setText("Status: Stopped")
        self.device_combo.setEnabled(True)
        self.buffer_spin.setEnabled(True)
        self.transcription_thread.stop()
        self.transcription_thread.wait()

    def update_transcription(self, text):
        self.text_display.append(text)
        # Auto-scroll to bottom
        scrollbar = self.text_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_error(self, error_message):
        self.status_label.setText(f"Status: Error - {error_message}")
        self.stop_transcription()

    def closeEvent(self, event):
        self.stop_transcription()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TranscriptionApp()
    window.show()
    sys.exit(app.exec_())
