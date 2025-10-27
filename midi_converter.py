"""Convert tracker format to MIDI artifacts with swing support."""

import mido
from typing import Dict, List, Optional

from config import RuntimeConfig
from tracker_parser import InstrumentTrack


class MIDIConverter:
    """Converts parsed tracker data to MIDI file or messages"""

    def __init__(self, runtime_config: RuntimeConfig, tempo: Optional[int] = None):
        """
        Initialize MIDI converter
        Args:
            runtime_config: Immutable runtime configuration.
            tempo: BPM override (defaults to runtime_config.tempo)
        """
        self.config = runtime_config
        self.tempo = tempo or runtime_config.tempo
        self.ticks_per_step = runtime_config.ticks_per_step

    def _calculate_swing_time(self, step_idx: int) -> int:
        """
        Calculate time position for a step with optional swing adjustment.

        Swing feel: off-beat 16th notes are delayed, creating a "long-short" feel.
        Example with 2:1 swing (ratio=0.67):
          - Steps 0,2,4,6... (on-beats): normal timing
          - Steps 1,3,5,7... (off-beats): delayed by 67% through the 8th note

        Args:
            step_idx: Step index (0-based)

        Returns:
            Time in MIDI ticks
        """
        if not self.config.swing_enabled:
            # No swing, or not 16th notes - use straight timing
            return step_idx * self.ticks_per_step

        # Determine if this is an on-beat or off-beat
        pair_idx = step_idx // 2  # Which 8th note pair (0, 1, 2, ...)
        is_offbeat = step_idx % 2 == 1

        # Calculate base time for this 8th note pair
        eighth_note_ticks = self.ticks_per_step * 2  # Two 16th notes = one 8th note
        base_time = pair_idx * eighth_note_ticks

        if is_offbeat:
            # Off-beat: delayed by swing ratio
            swing_delay = int(eighth_note_ticks * self.config.swing_ratio)
            return base_time + swing_delay
        else:
            # On-beat: normal timing
            return base_time

    def create_midi_file(self, tracks: Dict[str, InstrumentTrack]) -> mido.MidiFile:
        """
        Convert tracker data to MIDI file
        Args:
            tracks: Dict mapping instrument name to InstrumentTrack
        Returns:
            mido.MidiFile object
        """
        mid = mido.MidiFile(ticks_per_beat=self.config.ticks_per_beat)

        # Add tempo track
        tempo_track = mido.MidiTrack()
        mid.tracks.append(tempo_track)
        tempo_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(self.tempo)))

        # Add each instrument track
        for instrument_name, track_data in tracks.items():
            midi_track = self._convert_track(instrument_name, track_data)
            mid.tracks.append(midi_track)

        return mid

    def _convert_track(self, instrument_name: str, track_data: InstrumentTrack) -> mido.MidiTrack:
        """
        Convert a single instrument track to MIDI track
        Args:
            instrument_name: Name of instrument (BASS, DRUMS, PIANO, SAX)
            track_data: InstrumentTrack object
        Returns:
            mido.MidiTrack
        """
        track = mido.MidiTrack()
        channel = self.config.channels.get(instrument_name, 0)

        # Add track name
        track.append(mido.MetaMessage('track_name', name=instrument_name))

        # Set program (instrument) - skip for drums
        if instrument_name != 'DRUMS':
            program = self._get_program(instrument_name)
            track.append(mido.Message('program_change', program=program, channel=channel, time=0))

        # Track active notes (for both trigger and sustain modes)
        active_notes = {}  # pitch -> (velocity, start_time)

        # Convert each step
        current_time = 0  # Absolute time position in ticks

        for step_idx, step in enumerate(track_data.steps):
            step_start_time = self._calculate_swing_time(step_idx)

            if self.config.note_mode == 'trigger':
                # Trigger mode with tie support: notes hold across ties (^)

                if step.is_tie:
                    # Tie: continue previous notes, don't emit any events
                    # Just advance time
                    pass

                elif not step.is_rest:
                    # New note(s): turn off any active notes first, then start new ones

                    # Turn off active notes
                    if active_notes:
                        time_offset = max(0, step_start_time - current_time)
                        first_delta = True
                        for note_pitch in list(active_notes.keys()):
                            delta_time = time_offset if first_delta else 0
                            track.append(mido.Message(
                                'note_off',
                                note=note_pitch,
                                velocity=0,
                                channel=channel,
                                time=delta_time
                            ))
                            first_delta = False
                        active_notes.clear()
                        current_time = step_start_time

                    # Start new notes
                    for note_idx, note in enumerate(step.notes):
                        delta_time = step_start_time - current_time if note_idx == 0 else 0
                        track.append(mido.Message(
                            'note_on',
                            note=note.pitch,
                            velocity=note.velocity,
                            channel=channel,
                            time=delta_time
                        ))
                        if note_idx == 0:
                            current_time = step_start_time
                        active_notes[note.pitch] = (note.velocity, step_start_time)

                else:
                    # Rest: turn off any active notes
                    if active_notes:
                        time_offset = max(0, step_start_time - current_time)
                        first_delta = True
                        for note_pitch in list(active_notes.keys()):
                            delta_time = time_offset if first_delta else 0
                            track.append(mido.Message(
                                'note_off',
                                note=note_pitch,
                                velocity=0,
                                channel=channel,
                                time=delta_time
                            ))
                            first_delta = False
                        active_notes.clear()
                        current_time = step_start_time

            elif self.config.note_mode == 'sustain':
                # Sustain mode: notes hold until next event
                time_offset = max(0, step_start_time - current_time)
                first_delta = True

                if active_notes:
                    for note_pitch in list(active_notes):
                        delta_time = time_offset if first_delta else 0
                        track.append(mido.Message(
                            'note_off',
                            note=note_pitch,
                            velocity=0,
                            channel=channel,
                            time=delta_time
                        ))
                        first_delta = False
                    active_notes.clear()

                if not step.is_rest:
                    for note_idx, note in enumerate(step.notes):
                        delta_time = time_offset if first_delta and note_idx == 0 else 0
                        track.append(mido.Message(
                            'note_on',
                            note=note.pitch,
                            velocity=note.velocity,
                            channel=channel,
                            time=delta_time
                        ))
                        first_delta = False
                        active_notes.add(note.pitch)

                if not first_delta:
                    current_time = step_start_time

        # Turn off any remaining active notes
        for note_pitch in active_notes:
            track.append(mido.Message(
                'note_off',
                note=note_pitch,
                velocity=0,
                channel=channel,
                time=self.ticks_per_step
            ))

        # End of track
        track.append(mido.MetaMessage('end_of_track', time=0))

        return track

    def _calculate_swing_time_seconds(self, step_idx: int, time_per_step: float) -> float:
        """
        Calculate time position for a step in seconds with optional swing adjustment.

        Args:
            step_idx: Step index (0-based)
            time_per_step: Duration of one step in seconds (straight timing)

        Returns:
            Time in seconds
        """
        if not self.config.swing_enabled:
            # No swing, or not 16th notes - use straight timing
            return step_idx * time_per_step

        # Determine if this is an on-beat or off-beat
        pair_idx = step_idx // 2  # Which 8th note pair
        is_offbeat = step_idx % 2 == 1

        # Calculate base time for this 8th note pair
        eighth_note_duration = time_per_step * 2  # Two 16th notes = one 8th note
        base_time = pair_idx * eighth_note_duration

        if is_offbeat:
            # Off-beat: delayed by swing ratio
            swing_delay = eighth_note_duration * self.config.swing_ratio
            return base_time + swing_delay
        else:
            # On-beat: normal timing
            return base_time

    def _get_program(self, instrument_name: str) -> int:
        """
        Get General MIDI program number for instrument
        Returns:
            MIDI program number (0-127)
        """
        # General MIDI program numbers (0-indexed)
        programs = {
            'PIANO': 0,   # Acoustic Grand Piano
            'BASS': 33,   # Electric Bass (Finger) - louder than 32 (Acoustic Bass)
            'SAX': 65,    # Soprano Sax (can change to 66 for Alto, 67 for Tenor)
        }
        return programs.get(instrument_name, 0)

    def create_realtime_messages(
        self,
        tracks: Dict[str, InstrumentTrack],
        start_step: int = 0,
        num_steps: int = None
    ) -> List[tuple]:
        """
        Generate real-time MIDI messages for playback
        Args:
            tracks: Dict mapping instrument name to InstrumentTrack
            start_step: Starting step index
            num_steps: Number of steps to generate (None = all)
        Returns:
            List of (time_in_seconds, mido.Message) tuples
        """
        messages = []

        # Calculate time per step in seconds
        beats_per_second = self.tempo / 60.0
        steps_per_beat = 4  # Fixed 16th-note resolution
        time_per_step = 1.0 / (beats_per_second * steps_per_beat)

        # Generate messages for each instrument
        for instrument_name, track_data in tracks.items():
            channel = self.config.channels.get(instrument_name, 0)

            # Set program change at t=0
            if instrument_name != 'DRUMS':
                program = self._get_program(instrument_name)
                messages.append((0.0, mido.Message('program_change', program=program, channel=channel)))

            # Determine step range
            end_step = len(track_data.steps) if num_steps is None else start_step + num_steps
            steps_to_process = track_data.steps[start_step:end_step]

            # Track active notes for tie support
            active_notes = {}  # pitch -> (velocity, start_time)

            # Generate note events
            for step_idx, step in enumerate(steps_to_process):
                absolute_step = start_step + step_idx
                step_time = self._calculate_swing_time_seconds(absolute_step, time_per_step)

                if step.is_tie:
                    # Tie: continue previous notes, don't emit any events
                    pass

                elif not step.is_rest:
                    # New note(s): turn off any active notes first, then start new ones

                    # Turn off active notes
                    if active_notes and self.config.note_mode == 'trigger':
                        for note_pitch in list(active_notes.keys()):
                            messages.append((
                                step_time,
                                mido.Message('note_off', note=note_pitch, velocity=0, channel=channel)
                            ))
                        active_notes.clear()

                    # Note on
                    for note in step.notes:
                        messages.append((
                            step_time,
                            mido.Message('note_on', note=note.pitch, velocity=note.velocity, channel=channel)
                        ))
                        active_notes[note.pitch] = (note.velocity, step_time)

                else:
                    # Rest: turn off any active notes
                    if active_notes and self.config.note_mode == 'trigger':
                        for note_pitch in list(active_notes.keys()):
                            messages.append((
                                step_time,
                                mido.Message('note_off', note=note_pitch, velocity=0, channel=channel)
                            ))
                        active_notes.clear()

            # Turn off any remaining active notes at the end
            if active_notes and self.config.note_mode == 'trigger':
                final_step = start_step + len(steps_to_process)
                final_time = self._calculate_swing_time_seconds(final_step, time_per_step)
                for note_pitch in active_notes.keys():
                    messages.append((
                        final_time,
                        mido.Message('note_off', note=note_pitch, velocity=0, channel=channel)
                    ))

        # Sort by time
        messages.sort(key=lambda x: x[0])
        return messages


def tracker_to_midi_file(
    tracks: Dict[str, InstrumentTrack],
    runtime_config: RuntimeConfig,
    tempo: Optional[int] = None
) -> mido.MidiFile:
    """
    Convenience function: Convert tracker data to MIDI file
    Args:
        tracks: Dict mapping instrument name to InstrumentTrack
        runtime_config: Immutable runtime configuration.
        tempo: BPM override (defaults to runtime_config.tempo)
    Returns:
        mido.MidiFile
    """
    converter = MIDIConverter(runtime_config, tempo=tempo)
    return converter.create_midi_file(tracks)
