"""
uitars_server.py — BilalAgent v2.0 Phase 8
Manages the llama.cpp subprocess that serves UI-TARS as a vision-language API.
UI-TARS models are served via llama-server.exe (CPU-only, no GPU required).
"""

import os
import sys
import time
import signal
import logging
import subprocess
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Logging ─────────────────────────────────────
LOG_DIR = os.path.join(PROJECT_ROOT, "memory")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "uitars_server.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("uitars_server")


class UITARSServer:
    """
    Manages llama-server.exe subprocess serving UI-TARS vision models.
    
    Usage:
        server = UITARSServer()
        server.start("2b")      # Start 2B model (lighter, faster)
        server.start("7b")      # Start 7B model (better accuracy)
        server.stop()
    """

    # Model directories
    MODEL_PATHS = {
        "7b": r"D:\local_models\bartowski\UI-TARS-7B-SFT-GGUF",
        "2b": r"D:\local_models\bartowski\UI-TARS-2B-SFT-GGUF",
    }

    # llama.cpp server binary
    SERVER_EXE = r"D:\local_models\llama.cpp\llama-server.exe"

    # Server config
    PORT = 8081
    HOST = "127.0.0.1"
    CTX_SIZE = 4096
    N_GPU_LAYERS = 0  # CPU only — Honor MagicBook 16 has no dedicated GPU

    # GGUF preference order (best quality first within size constraints)
    GGUF_PREFERENCE = ["Q4_K_M", "Q4_K", "Q4_K_S", "Q4", "Q2_K"]

    def __init__(self):
        self._process = None
        self._current_model = None
        self._gguf_path = None
        self._log_path = os.path.join(LOG_DIR, "uitars_server.log")

    def _find_gguf(self, folder: str) -> str:
        """
        Scan folder for .gguf files and return the best one by quantization preference.
        Skips mmproj files (those are vision projector weights, loaded separately).
        
        Args:
            folder: Directory containing GGUF files
            
        Returns:
            Full path to best GGUF file, or None if not found
        """
        if not os.path.isdir(folder):
            log.error(f"[UITARSServer] Model directory not found: {folder}")
            return None

        gguf_files = [f for f in os.listdir(folder) 
                      if f.endswith(".gguf") and not f.startswith("mmproj")]

        if not gguf_files:
            log.error(f"[UITARSServer] No GGUF files found in {folder}")
            return None

        # Try preference order
        for pref in self.GGUF_PREFERENCE:
            for f in gguf_files:
                if pref in f:
                    return os.path.join(folder, f)

        # Fallback: first non-mmproj GGUF
        return os.path.join(folder, gguf_files[0])

    def _find_mmproj(self, folder: str) -> str:
        """
        Find the multimodal projector file (mmproj-*.gguf) for vision support.
        
        Args:
            folder: Directory containing GGUF files
            
        Returns:
            Full path to mmproj file, or None
        """
        if not os.path.isdir(folder):
            return None

        mmproj_files = [f for f in os.listdir(folder) 
                        if f.endswith(".gguf") and f.startswith("mmproj")]

        if mmproj_files:
            return os.path.join(folder, mmproj_files[0])
        return None

    def start(self, model: str = "2b") -> bool:
        """
        Start the UI-TARS llama.cpp server.
        
        Args:
            model: "2b" or "7b" — which UI-TARS model to load
            
        Returns:
            True if server started successfully, False on failure/timeout
        """
        if model not in self.MODEL_PATHS:
            log.error(f"[UITARSServer] Unknown model size: {model}. Use '2b' or '7b'.")
            return False

        # Stop existing server if running
        if self._process is not None:
            log.info("[UITARSServer] Stopping existing server before starting new one...")
            self.stop()

        # Find GGUF file
        folder = self.MODEL_PATHS[model]
        gguf_path = self._find_gguf(folder)
        if not gguf_path:
            log.error(f"[UITARSServer] No GGUF file found in {folder}")
            return False

        # Find mmproj file for vision
        mmproj_path = self._find_mmproj(folder)

        # Verify server binary exists
        if not os.path.exists(self.SERVER_EXE):
            log.error(f"[UITARSServer] Server binary not found: {self.SERVER_EXE}")
            return False

        # Build command
        cmd = [
            self.SERVER_EXE,
            "-m", gguf_path,
            "--port", str(self.PORT),
            "--ctx-size", str(self.CTX_SIZE),
            "-ngl", str(self.N_GPU_LAYERS),
            "--host", self.HOST,
        ]

        # Add mmproj if found (required for vision/multimodal)
        if mmproj_path:
            cmd.extend(["--mmproj", mmproj_path])
            log.info(f"[UITARSServer] Using mmproj: {os.path.basename(mmproj_path)}")

        log.info(f"[UITARSServer] Starting {model} model...")
        log.info(f"[UITARSServer] GGUF: {os.path.basename(gguf_path)}")
        log.info(f"[UITARSServer] Command: {' '.join(cmd)}")

        # Launch subprocess
        try:
            log_file = open(self._log_path, "a", encoding="utf-8")
            log_file.write(f"\n{'='*60}\n")
            log_file.write(f"Starting UI-TARS {model} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"{'='*60}\n")
            log_file.flush()

            self._process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self._current_model = model
            self._gguf_path = gguf_path

        except Exception as e:
            log.error(f"[UITARSServer] Failed to launch: {e}")
            return False

        # Poll /health until ready (up to 90 seconds)
        health_url = f"http://{self.HOST}:{self.PORT}/health"
        log.info(f"[UITARSServer] Waiting for server to be ready (polling {health_url})...")

        start_time = time.time()
        timeout = 90
        poll_interval = 2

        while time.time() - start_time < timeout:
            # Check if process died
            if self._process.poll() is not None:
                log.error(f"[UITARSServer] Process exited with code {self._process.returncode}")
                self._process = None
                return False

            try:
                resp = requests.get(health_url, timeout=2)
                if resp.status_code == 200:
                    elapsed = time.time() - start_time
                    log.info(f"[UITARSServer] Started {model} on port {self.PORT} ({elapsed:.1f}s)")
                    return True
            except requests.ConnectionError:
                pass
            except requests.Timeout:
                pass

            time.sleep(poll_interval)

        # Timeout
        log.error(f"[UITARSServer] Timeout after {timeout}s waiting for server")
        self.stop()
        return False

    def stop(self):
        """Stop the llama.cpp server subprocess."""
        if self._process is None:
            log.info("[UITARSServer] No server process to stop")
            return

        log.info("[UITARSServer] Stopping server...")

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning("[UITARSServer] Process didn't terminate gracefully, killing...")
                self._process.kill()
                self._process.wait(timeout=5)
        except Exception as e:
            log.error(f"[UITARSServer] Error stopping server: {e}")
        finally:
            self._process = None
            self._current_model = None
            log.info("[UITARSServer] Stopped")

    def is_running(self) -> bool:
        """Check if UI-TARS server is responding on its port."""
        try:
            resp = requests.get(f"http://{self.HOST}:{self.PORT}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Return current server status and model info."""
        return {
            "running": self.is_running(),
            "model_size": self._current_model,
            "port": self.PORT,
            "gguf_path": self._gguf_path,
            "log_path": self._log_path,
        }

    def __del__(self):
        """Clean up on garbage collection."""
        if self._process is not None:
            try:
                self.stop()
            except Exception:
                pass


# ─── Module-Level Convenience ────────────────────

_server_instance = None


def get_server() -> UITARSServer:
    """Get or create the singleton UITARSServer instance."""
    global _server_instance
    if _server_instance is None:
        _server_instance = UITARSServer()
    return _server_instance


if __name__ == "__main__":
    print("=" * 50)
    print("UI-TARS Server Test")
    print("=" * 50)

    server = UITARSServer()

    # Find GGUF files
    for size in ["2b", "7b"]:
        folder = server.MODEL_PATHS[size]
        gguf = server._find_gguf(folder)
        mmproj = server._find_mmproj(folder)
        print(f"\n{size.upper()}:")
        print(f"  GGUF: {gguf}")
        print(f"  MMProj: {mmproj}")

    print(f"\nServer exe: {server.SERVER_EXE}")
    print(f"Exists: {os.path.exists(server.SERVER_EXE)}")
