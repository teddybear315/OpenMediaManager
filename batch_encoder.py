"""
Batch Encoder for Open Media Manager
Handles re-encoding of media files using ffmpeg.
"""

import subprocess
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from media_scanner import MediaInfo, MediaStatus


class EncodingMode(Enum):
    """Encoding modes available."""
    SELECTED = "selected"  # Re-encode selected files
    HIGH_QUALITY = "hq"  # Re-encode only high-quality sources


@dataclass
class EncodingJob:
    """Represents a single encoding job."""
    media_info: MediaInfo
    output_path: Path
    status: str = "pending"
    progress: float = 0.0
    error_message: str = ""


class BatchEncoder(QObject):
    """Handles batch encoding of media files."""
    
    # Signals for progress updates
    progress_signal = pyqtSignal(int, float, str, float, str)  # job_index, progress, status, speed, eta
    job_complete = pyqtSignal(int, bool, str)  # job_index, success, message
    all_complete = pyqtSignal()
    log_signal = pyqtSignal(str, str, str)  # log_type, message, color
    
    def __init__(self, encoding_params: Dict[str, Any], naming_params: Dict[str, Any]):
        """
        Initialize the batch encoder.
        
        Args:
            encoding_params: Dictionary of encoding parameters from config.
            naming_params: Dictionary of naming parameters from config.
        """
        super().__init__()
        self.encoding_params = encoding_params
        self.naming_params = naming_params
        self.jobs: List[EncodingJob] = []
        self.is_running = False
        self.should_stop = False
        self.current_process: Optional[subprocess.Popen] = None
    
    def prepare_jobs(self, media_files: List[MediaInfo], mode: EncodingMode = EncodingMode.SELECTED) -> List[EncodingJob]:
        """
        Prepare encoding jobs from media files.
        
        Args:
            media_files: List of MediaInfo objects to encode.
            mode: Encoding mode (selected or high quality only).
            
        Returns:
            List of EncodingJob objects.
        """
        from media_scanner import MediaCategory
        jobs = []
        ignore_extras = self.encoding_params.get("ignore_extras", True)
        
        for media_info in media_files:
            # Skip files that are compliant or below standard (low bitrate)
            if media_info.status == MediaStatus.COMPLIANT:
                continue
            
            if media_info.status == MediaStatus.BELOW_STANDARD:
                continue
            
            # Skip extras if ignore_extras is enabled
            if ignore_extras and media_info.category == MediaCategory.EXTRA:
                continue
            
            # For HQ mode, only process high-resolution sources
            if mode == EncodingMode.HIGH_QUALITY:
                if media_info.height < 1080:
                    continue
            
            # Create output path
            output_path = self._generate_output_path(media_info)
            
            job = EncodingJob(
                media_info=media_info,
                output_path=output_path
            )
            jobs.append(job)
        
        self.jobs = jobs
        return jobs
    
    def start_encoding(self):
        """Start the batch encoding process."""
        if self.is_running or not self.jobs:
            return
        
        self.is_running = True
        self.should_stop = False
        
        for idx, job in enumerate(self.jobs):
            if self.should_stop:
                break
            
            self._encode_job(idx, job)
        
        self.is_running = False
        self.all_complete.emit()
    
    def stop_encoding(self):
        """Stop the batch encoding process."""
        print("[STOP] Stop encoding requested")
        self.should_stop = True
        
        # Immediately kill the current ffmpeg process if running
        if self.current_process and self.current_process.poll() is None:
            try:
                pid = self.current_process.pid
                print(f"[STOP] Killing ffmpeg process (PID: {pid}) and its tree")
                import os
                if os.name == 'nt':
                    # Use taskkill to remove the whole process tree on Windows
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=False)
                    print("[STOP] taskkill invoked for PID", pid)
                else:
                    # POSIX: kill the process group
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, 9)
                        print("[STOP] Killed process group", pgid)
                    except Exception:
                        # Fallback to killing the single process
                        try:
                            self.current_process.kill()
                        except Exception:
                            pass
                print("[STOP] FFmpeg kill sequence complete")
            except subprocess.TimeoutExpired:
                print(f"[STOP] Process {self.current_process.pid} did not die, forcing")
                import signal
                import os
                try:
                    if os.name == 'nt':
                        # Use taskkill to remove process tree on Windows
                        subprocess.run(['taskkill', '/PID', str(self.current_process.pid), '/T', '/F'], check=False)
                    else:
                        os.kill(self.current_process.pid, signal.SIGKILL)
                except Exception:
                    pass
            except Exception as e:
                print(f"[WARNING] Could not kill ffmpeg process: {e}")
            finally:
                try:
                    self.current_process = None
                except Exception:
                    pass
    
    def stop(self):
        """Compatibility alias for GUI: call `stop_encoding()`.

        Some GUI code connects to `encoder.stop` — provide a small
        wrapper so existing signal connections work.
        """
        return self.stop_encoding()

    def generate_comparison_report(self) -> str:
        """
        Generate a comparison report of encoding results.
        
        Returns:
            String containing the comparison report.
        """
        report_lines = []
        report_lines.append("="*60)
        report_lines.append("ENCODING COMPARISON REPORT")
        report_lines.append("="*60)
        report_lines.append("")
        
        successful_jobs = [job for job in self.jobs if job.status == "complete" and job.output_path.exists()]
        
        if not successful_jobs:
            report_lines.append("No successful encodings to report.")
            return "\n".join(report_lines)
        
        total_original_size = 0
        total_new_size = 0
        
        for job in successful_jobs:
            original_size = job.media_info.file_size
            new_size = job.output_path.stat().st_size
            
            total_original_size += original_size
            total_new_size += new_size
            
            size_diff = original_size - new_size
            percentage = (size_diff / original_size * -100) if original_size > 0 else 0
            
            # Format sizes
            orig_gb = original_size / (1024**3)
            new_gb = new_size / (1024**3)
            
            if orig_gb < 1:
                orig_str = f"{original_size/(1024**2):.2f} MB"
            else:
                orig_str = f"{orig_gb:.2f} GB"
            
            if new_gb < 1:
                new_str = f"{new_size/(1024**2):.2f} MB"
            else:
                new_str = f"{new_gb:.2f} GB"
            
            report_lines.append(f"File: {job.media_info.filename}")
            report_lines.append(f"  Original: {orig_str}")
            report_lines.append(f"  Encoded:  {new_str}")
            report_lines.append(f"  Reduction: {percentage:+.2f}%")
            report_lines.append("")
        
        # Overall summary
        overall_diff = total_original_size - total_new_size
        overall_pct = (overall_diff / total_original_size * -100) if total_original_size > 0 else 0
        
        report_lines.append("="*60)
        report_lines.append("OVERALL SUMMARY")
        report_lines.append("="*60)
        report_lines.append(f"Total Files: {len(successful_jobs)}")
        report_lines.append(f"Original Size: {total_original_size/(1024**3):.2f} GB")
        report_lines.append(f"Encoded Size:  {total_new_size/(1024**3):.2f} GB")
        report_lines.append(f"Total Reduction: {overall_pct:+.2f}%")
        report_lines.append(f"Space Saved: {overall_diff/(1024**3):.2f} GB")
        report_lines.append("="*60)
        
        return "\n".join(report_lines)
    
    def save_comparison_report(self, output_dir: Path) -> Path:
        """
        Save comparison report to file.
        
        Args:
            output_dir: Directory containing encoded files.
            
        Returns:
            Path to the saved report file.
        """
        report_content = self.generate_comparison_report()
        report_file = output_dir / "encoding_comparison.txt"
        
        with open(report_file, 'w') as f:
            f.write(report_content)
        
        return report_file
    
    def _encode_job(self, job_index: int, job: EncodingJob):
        """
        Encode a single media file.
        
        Args:
            job_index: Index of the job in the jobs list.
            job: EncodingJob to process.
        """
        try:
            job.status = "encoding"
            self.progress_signal.emit(job_index, 0.0, "Starting encoding...", 0.0, "--:--")
            
            # Log file start
            self.log_signal.emit("file_start", f"{str(job.media_info.path)}|{str(job.output_path)}", "")
            
            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(job.media_info, job.output_path)
            
            # Log the command
            cmd_str = ' '.join(cmd)
            print(f"[ENCODE CMD] {cmd_str}")
            self.log_signal.emit("command", cmd_str, "")
            
            # Create output directory if needed
            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Run ffmpeg with stats output. Start in its own process group/session
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            import os
            if os.name == 'nt':
                # CREATE_NEW_PROCESS_GROUP allows sending CTRL_BREAK_EVENT and taskkill /T to remove tree
                popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # POSIX: start a new session so we can kill the process group
                popen_kwargs['start_new_session'] = True

            self.current_process = subprocess.Popen(cmd, **popen_kwargs)
            process = self.current_process
            
            # Monitor progress with non-blocking read
            duration = job.media_info.duration
            source_fps = job.media_info.fps
            total_frames = duration * source_fps if source_fps > 0 else 0
            import select
            import sys
            
            try:
                for line in iter(process.stderr.readline, ''):
                    if not line:
                        break
                    
                    if self.should_stop:
                        # Kill process immediately
                        if process.poll() is None:
                            process.kill()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            print("[WARNING] Process did not terminate, forcing kill")
                            process.kill()
                            process.wait()
                        
                        # Delete partial output file
                        try:
                            if job.output_path.exists():
                                job.output_path.unlink()
                                print(f"[INFO] Deleted partial file: {job.output_path}")
                        except Exception as e:
                            print(f"[WARNING] Could not delete partial file {job.output_path}: {e}")
                        
                        job.status = "cancelled"
                        self.job_complete.emit(job_index, False, "Cancelled by user")
                        return
                    
                    # Parse ffmpeg progress output (frame=, fps=, time=, speed= are typically on same line)
                    if "frame=" in line and "time=" in line:
                        try:
                            # Extract current frame number
                            current_frame = 0
                            try:
                                frame_str = line.split("frame=")[1].split()[0].strip()
                                current_frame = int(frame_str)
                            except (ValueError, IndexError):
                                pass
                            
                            # Extract time for fallback progress calculation
                            current_time = 0.0
                            try:
                                time_str = line.split("time=")[1].split()[0]
                                parts = time_str.split(":")
                                if len(parts) == 3:
                                    h, m, s = parts
                                    current_time = float(h) * 3600 + float(m) * 60 + float(s)
                                elif len(parts) == 2:
                                    m, s = parts
                                    current_time = float(m) * 60 + float(s)
                                else:
                                    current_time = float(parts[0])
                            except Exception:
                                pass
                            
                            # Calculate progress from frames if available, otherwise use time
                            if total_frames > 0 and current_frame > 0:
                                progress = (current_frame / total_frames) * 100
                            elif current_time > 0 and duration > 0:
                                progress = (current_time / duration) * 100
                            else:
                                continue

                            # Extract encoding FPS (speed in frames per second)
                            encoding_fps = 0.0
                            try:
                                fps_str = line.split("fps=")[1].split()[0].strip()
                                encoding_fps = float(fps_str)
                            except (ValueError, IndexError):
                                pass
                            
                            # Extract speed multiplier for display
                            speed = 0.0
                            try:
                                speed_str = line.split("speed=")[1].split('x')[0].strip()
                                speed = float(speed_str)
                            except (ValueError, IndexError):
                                pass

                            # Calculate ETA using frame-based method
                            eta = "--:--"
                            if encoding_fps > 0 and total_frames > 0 and current_frame > 0:
                                frames_remaining = max(0, total_frames - current_frame)
                                remaining_seconds = frames_remaining / encoding_fps
                                eta_minutes = int(remaining_seconds // 60)
                                eta_seconds = int(remaining_seconds % 60)
                                eta = f"{eta_minutes:02d}:{eta_seconds:02d}"

                            self.progress_signal.emit(job_index, progress, "Encoding...", encoding_fps, eta)
                        except Exception as e:
                            # Log parsing errors for debugging
                            print(f"[DEBUG] Progress parsing error: {e}")
                            pass
            
            finally:
                # Wait for process to complete
                try:
                    process.wait()
                except Exception:
                    pass

                # Ensure all ffmpeg instances are gone on Windows when stopping
                try:
                    import os
                    if self.should_stop and os.name == 'nt':
                        # Brute-force any lingering ffmpeg.exe instances
                        subprocess.run(['taskkill', '/IM', 'ffmpeg.exe', '/F', '/T'], check=False)
                except Exception:
                    pass

                # Clear current process reference
                self.current_process = None

            # Handle stop/cancellation after finally block
            if self.should_stop:
                try:
                    import time
                    attempts = 5
                    deleted = False
                    for _ in range(attempts):
                        try:
                            if job.output_path.exists():
                                job.output_path.unlink()
                                print(f"[INFO] Deleted partial file after stop: {job.output_path}")
                                deleted = True
                                break
                            else:
                                deleted = True
                                break
                        except Exception as e:
                            last_exc = e
                            time.sleep(0.5)
                    if not deleted:
                        print(f"[WARNING] Could not delete partial file {job.output_path}: {last_exc}")
                except Exception as e:
                    print(f"[WARNING] Error while deleting partial file: {e}")

                job.status = "cancelled"
                self.job_complete.emit(job_index, False, "Cancelled by user")
                return
            
            if process.returncode == 0:
                # Check if output file was created and has content
                if job.output_path.exists() and job.output_path.stat().st_size > 0:
                    job.status = "complete"

                    # Compare file sizes
                    original_size = job.media_info.file_size
                    new_size = job.output_path.stat().st_size
                    size_diff = original_size - new_size
                    size_diff_pct = (size_diff / original_size * 100) if original_size > 0 else 0

                    # Optionally rename if configured
                    if self.naming_params.get("rename_files", True):
                        self._rename_output(job)

                    self.progress_signal.emit(job_index, 100.0, "Complete", 0.0, "00:00")

                    # Include size comparison in completion message
                    size_msg = f"Encoding successful. Size: {original_size/(1024**2):.1f}MB → {new_size/(1024**2):.1f}MB ({size_diff_pct:+.1f}%)"
                    self.job_complete.emit(job_index, True, size_msg)
                else:
                    job.status = "failed"
                    job.error_message = "Output file is empty or missing"
                    self.job_complete.emit(job_index, False, job.error_message)
            else:
                job.status = "failed"
                job.error_message = f"FFmpeg exited with code {process.returncode}"
                self.job_complete.emit(job_index, False, job.error_message)
        
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            self.job_complete.emit(job_index, False, str(e))
    
    def _build_ffmpeg_command(self, media_info: MediaInfo, output_path: Path) -> List[str]:
        """
        Build ffmpeg command for encoding.
        
        Args:
            media_info: MediaInfo object for source file.
            output_path: Path for output file.
            
        Returns:
            List of command arguments.
        """
        cmd = ['ffmpeg', '-hide_banner']

        # We'll determine whether to request hardware acceleration after codec availability check.
        cmd.extend(['-i', str(media_info.path)])
        
        # Check skip options
        skip_video = self.encoding_params.get("skip_video_encoding", False)
        skip_audio = self.encoding_params.get("skip_audio_encoding", False)
        skip_subs = self.encoding_params.get("skip_subtitle_encoding", False)
        
        # Video encoding parameters
        if skip_video:
            cmd.extend(['-c:v', 'copy'])
        else:
            # Prefer an explicit codec specified in encoding_params, otherwise compute
            codec = self.encoding_params.get("codec")
            use_gpu = self.encoding_params.get("use_gpu", False)
            if not codec:
                # Select codec based on codec_type and GPU setting
                if self.encoding_params.get("codec_type") == "av1":
                    codec = "av1_nvenc" if use_gpu else "libsvtav1"
                else:
                    codec = "hevc_nvenc" if use_gpu else "libx265"
            
            # If GPU codec requested, verify ffmpeg actually supports the encoder; if not, fall back.
            try:
                if 'nvenc' in codec.lower():
                    # Check ffmpeg encoders list for the requested nvenc codec
                    import subprocess
                    enc_list = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
                    if codec.lower() not in enc_list.stdout.lower():
                        # Fallback to software codec
                        fallback = 'libx265'
                        self.log_signal.emit('warning', f"Requested GPU encoder '{codec}' not available; falling back to {fallback}", '#ffa500')
                        codec = fallback
                        use_gpu = False
            except Exception:
                # If check fails, silently continue using requested codec
                pass

            cmd.extend(['-c:v', codec])
        
            # Profile (main or main10 for 10-bit)
            bit_depth_pref = self.encoding_params.get("bit_depth_preference", "source")
            if bit_depth_pref == "force_10bit" or (bit_depth_pref == "source" and media_info.bit_depth >= 10):
                profile = "main10"
            else:
                profile = "main"
            cmd.extend(['-profile:v', profile])
            
            # Check if using target bitrate (needed for both lossless and normal encoding)
            use_target_bitrate = self.encoding_params.get("use_target_bitrate", False)
            
            # Preset - CLI tool uses 'p6' for NVENC but that may be wrong, use faster for compatibility
            preset = self.encoding_params.get("preset", "medium")
            if use_gpu:
                preset = 'p6'  # NVENC uses p0-p7, p6 is high quality
            cmd.extend(['-preset', preset])
            
            # Tune animation
            if self.encoding_params.get("tune_animation", False) and "nvenc" not in codec:
                cmd.extend(['-tune', 'animation'])
            
            # Constant quality (only if not using target bitrate)
            if not use_target_bitrate:
                cq = self.encoding_params.get("cq", 22)
                if "nvenc" in codec:
                    # GPU encoding: use vbr mode with qp and qmax (like CLI tool)
                    cmd.extend(['-rc', 'vbr', '-qp', str(cq), '-qmax', str(cq + 3)])
                elif "svtav1" in codec:
                    # SVT-AV1 uses -crf
                    cmd.extend(['-crf', str(cq)])
                else:
                    # CPU encoding: use vbr with crf (like CLI tool)
                    cmd.extend(['-rc', 'vbr', '-crf', str(cq)])
            
            # Add aq-mode for better quality (from CLI tool)
            if "nvenc" not in codec:
                cmd.extend(['-aq-mode', '2'])
        
        # Bitrate limits and target bitrate
        use_bitrate_limits = self.encoding_params.get("use_bitrate_limits", False)
        # use_target_bitrate already defined above when checking CQ settings
        
        # If we still plan to request GPU acceleration, add hwaccel BEFORE encoding (only when available)
        if self.encoding_params.get('use_gpu', False) and ('nvenc' in (self.encoding_params.get('codec') or '').lower() or 'nvenc' in codec.lower()):
            # Insert hwaccel early in command if not already present
            if '-hwaccel' not in cmd:
                cmd.insert(1, 'auto')
                cmd.insert(1, '-hwaccel')

        if use_target_bitrate or use_bitrate_limits:
            # Determine resolution-specific bitrate
            height = media_info.height
            if height >= 2160:
                target_bitrate = self.encoding_params.get("target_bitrate_4k", 8000)
                bitrate_min = self.encoding_params.get("encoding_bitrate_min_4k", 6000)
                bitrate_max = self.encoding_params.get("encoding_bitrate_max_4k", 10000)
            elif height >= 1440:
                target_bitrate = self.encoding_params.get("target_bitrate_1440p", 5000)
                bitrate_min = self.encoding_params.get("encoding_bitrate_min_1440p", 3000)
                bitrate_max = self.encoding_params.get("encoding_bitrate_max_1440p", 6000)
            elif height >= 1080:
                target_bitrate = self.encoding_params.get("target_bitrate_1080p", 3000)
                bitrate_min = self.encoding_params.get("encoding_bitrate_min_1080p", 1500)
                bitrate_max = self.encoding_params.get("encoding_bitrate_max_1080p", 4000)
            elif height >= 720:
                target_bitrate = self.encoding_params.get("target_bitrate_720p", 1500)
                bitrate_min = self.encoding_params.get("encoding_bitrate_min_720p", 1000)
                bitrate_max = self.encoding_params.get("encoding_bitrate_max_720p", 2000)
            else:  # Below 720p (low res)
                target_bitrate = self.encoding_params.get("target_bitrate_low_res", 800)
                bitrate_min = self.encoding_params.get("encoding_bitrate_min_low_res", 500)
                bitrate_max = self.encoding_params.get("encoding_bitrate_max_low_res", 1000)
            
            # Apply target bitrate if enabled (works with CQ mode)
            if use_target_bitrate:
                cmd.extend(['-b:v', f'{target_bitrate}k'])
            
            # Apply min/max limits if enabled
            if use_bitrate_limits:
                cmd.extend(['-minrate', f'{bitrate_min}k', '-maxrate', f'{bitrate_max}k'])
        
        # Legacy bitrate settings (for backward compatibility if neither new mode is enabled)
        if not use_bitrate_limits and not use_target_bitrate:
            bitrate_min = self.encoding_params.get("bitrate_min", "")
            bitrate_max = self.encoding_params.get("bitrate_max", "")
            if bitrate_min and bitrate_max:
                cmd.extend(['-b:v', bitrate_max, '-minrate', bitrate_min, '-maxrate', bitrate_max])
        
        # Level (only if not skipping video)
        if not skip_video:
            level = self.encoding_params.get("level", "4.0")
            cmd.extend(['-level', level])
        
        # Pixel format - set for both CPU and GPU (GPU uses p010le for 10-bit)
        if not skip_video:
            use_gpu = self.encoding_params.get("use_gpu", False)
            bit_depth_pref = self.encoding_params.get("bit_depth_preference", "source")
            
            # Determine if 10-bit encoding
            use_10bit = bit_depth_pref == "force_10bit" or (bit_depth_pref == "source" and media_info.bit_depth >= 10)
            
            if use_gpu:
                # GPU: use p010le for 10-bit, yuv420p for 8-bit
                pix_fmt = 'p010le' if use_10bit else 'yuv420p'
            else:
                # CPU: use yuv420p10le for 10-bit, yuv420p for 8-bit
                pix_fmt = 'yuv420p10le' if use_10bit else 'yuv420p'
            
            cmd.extend(['-pix_fmt', pix_fmt])
        
        # Threads (only for CPU encoding)
        if not skip_video and not use_gpu:
            threads = self.encoding_params.get("thread_count", 4)
            cmd.extend(['-threads', str(threads)])
        
        # Map streams and specify codecs
        # Map video stream(s) - optionally skip cover art/attached pictures
        skip_cover_art = self.encoding_params.get("skip_cover_art", True)
        if skip_cover_art:
            # Map ONLY the first video stream to avoid encoding cover art/attached pictures
            cmd.extend(['-map', '0:v:0'])
        else:
            # Map all video streams including cover art
            cmd.extend(['-map', '0:v'])
        
        # Map audio streams - always copy when skip_audio is enabled
        cmd.extend(['-map', '0:a?'])
        if skip_audio:
            # Copy audio without re-encoding
            cmd.extend(['-c:a', 'copy'])
        else:
            # Copy audio (could add re-encoding logic here if needed)
            cmd.extend(['-c:a', 'copy'])
        
        # Map subtitle streams - always copy when skip_subs is enabled
        cmd.extend(['-map', '0:s?'])
        if skip_subs:
            # Copy subtitles without re-encoding
            cmd.extend(['-c:s', 'copy'])
        else:
            # Copy subtitles (could add re-encoding logic here if needed)
            cmd.extend(['-c:s', 'copy'])
        
        # Overwrite output
        cmd.append('-y')
        
        # Progress output
        cmd.extend(['-progress', 'pipe:2'])
        
        # Output file
        cmd.append(str(output_path))
        
        return cmd
    
    def _generate_output_path(self, media_info: MediaInfo) -> Path:
        """
        Generate output path for encoded file.
        
        Args:
            media_info: MediaInfo object for source file.
            
        Returns:
            Path object for output file.
        """
        # Create output in same directory with .tmp extension during encoding
        output_dir = media_info.path.parent / "encoded"
        output_dir.mkdir(exist_ok=True)
        
        # Use original filename for now
        filename = media_info.filename
        stem = Path(filename).stem
        ext = Path(filename).suffix
        
        output_path = output_dir / f"{stem}.encoded{ext}"
        
        return output_path
    
    def _rename_output(self, job: EncodingJob):
        """
        Rename output file according to naming conventions.
        
        Args:
            job: EncodingJob with completed encoding.
        """
        media_info = job.media_info
        
        # If it's a show, format as S##E## format
        if media_info.is_show and media_info.season is not None and media_info.episode is not None:
            show_name = media_info.show_name or "Show"
            
            # Clean up show name
            if self.naming_params.get("replace_periods", True):
                show_name = show_name.replace('.', ' ').replace('_', ' ')
            
            season_str = f"S{media_info.season:02d}"
            episode_str = f"E{media_info.episode:02d}"
            
            # Extract title from filename if available
            # Format: ShowName S##E## - EpisodeTitle.ext
            ext = job.output_path.suffix
            
            # Try to extract episode title from original filename
            original_name = media_info.filename
            title_part = ""
            
            # Look for text after episode marker
            import re
            match = re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}[\s._-]*(.+?)(?:\.[^.]+)?$', original_name)
            if match:
                title_part = match.group(1).strip()
                # Clean up title
                title_part = re.sub(r'[._-]+', ' ', title_part).strip()
                if title_part:
                    title_part = f" - {title_part}"
            
            new_filename = f"{show_name} {season_str}{episode_str}{title_part}{ext}"
            new_path = job.output_path.parent / new_filename
            
            try:
                job.output_path.rename(new_path)
                job.output_path = new_path
            except OSError:
                pass  # Keep original name if rename fails
        else:
            # For movies or files without episode info, just clean up the name
            if self.naming_params.get("replace_periods", True):
                stem = job.output_path.stem
                ext = job.output_path.suffix
                cleaned_name = stem.replace('.', ' ').replace('_', ' ')
                new_path = job.output_path.parent / f"{cleaned_name}{ext}"
                
                try:
                    job.output_path.rename(new_path)
                    job.output_path = new_path
                except OSError:
                    pass


class EncodingThread(QThread):
    """Thread for running encoding jobs in background."""
    
    progress_signal = pyqtSignal(int, float, str, float, str)  # job_index, progress, status, speed, eta
    job_complete = pyqtSignal(int, bool, str)
    all_complete = pyqtSignal()
    
    def __init__(self, encoder: BatchEncoder):
        """
        Initialize encoding thread.
        
        Args:
            encoder: BatchEncoder instance to run.
        """
        super().__init__()
        self.encoder = encoder
        
        # Connect encoder signals to thread signals
        self.encoder.progress_signal.connect(self.progress_signal.emit)
        self.encoder.job_complete.connect(self.job_complete.emit)
        self.encoder.all_complete.connect(self.all_complete.emit)
    
    def run(self):
        """Run the encoding process."""
        self.encoder.start_encoding()
