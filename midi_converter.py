"""Convert tracker format to MIDI artifacts with swing support."""

import mido
from typing import Dict, List, Optional

from config import RuntimeConfig
from tracker_parser import InstrumentTrack


class MIDIConverter:
    """Converts parsed tracker data to MIDI file or messages"""

    def __init__(self, runtime_config: RuntimeConfig, tempo: Optional[int] = None, translate_drums: Optional[bool] = None, transpose_octaves: Optional[int] = None):
        """
        Initialize MIDI converter
        Args:
            runtime_config: Immutable runtime configuration.
            tempo: BPM override (defaults to runtime_config.tempo)
            translate_drums: Override drum translation setting (None = use config default)
            transpose_octaves: Override octave transposition (None = use config default)
        """
        self.config = runtime_config
        self.tempo = tempo or runtime_config.tempo
        self.ticks_per_step = runtime_config.ticks_per_step
        # Allow override of drum translation
        self.translate_drums = translate_drums if translate_drums is not None else runtime_config.translate_drums
        # Allow override of transposition
        self.transpose_octaves = transpose_octaves if transpose_octaves is not None else runtime_config.transpose_octaves
        # Track which instruments have had program changes sent (for realtime playback)
        self._programs_sent = set()

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

    def _translate_note(self, note_pitch: int, instrument_name: str) -> int:
        """
        Translate MIDI note number for hardware-specific mappings.

        Args:
            note_pitch: Original MIDI note number (e.g., GM drum note)
            instrument_name: Instrument name (used to detect drums)

        Returns:
            Translated MIDI note number for hardware
        """
        # Translate drums if enabled and this is the drum track
        if instrument_name == 'DRUMS' and self.translate_drums:
            return self.config.drum_mapping.get(note_pitch, note_pitch)

        # Transpose melodic instruments (not drums) by octaves
        if instrument_name != 'DRUMS' and self.transpose_octaves != 0:
            transposed = note_pitch + (self.transpose_octaves * 12)
            # Clamp to valid MIDI range
            return max(0, min(127, transposed))

        return note_pitch

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
        if instrument_name != 'DRUMS' and self.config.send_program_changes:
            program = self.config.programs.get(instrument_name, 0)
            track.append(mido.Message('program_change', program=program, channel=channel, time=0))

        # Track active notes (dict in trigger mode, set in sustain mode)
        active_notes = {} if self.config.note_mode == 'trigger' else set()

        last_event_time = 0  # Absolute tick position of the last emitted MIDI event

        for step_idx, step in enumerate(track_data.steps):
            step_start_time = self._calculate_swing_time(step_idx)
            delta = max(0, step_start_time - last_event_time)

            if self.config.note_mode == 'trigger':
                if step.is_tie:
                    # Continue sustaining existing notes; nothing to emit
                    pass
                elif not step.is_rest:
                    # Turn off previous notes before starting new ones
                    if active_notes:
                        for note_pitch in list(active_notes.keys()):
                            track.append(mido.Message(
                                'note_off',
                                note=note_pitch,
                                velocity=0,
                                channel=channel,
                                time=delta
                            ))
                            delta = 0
                            last_event_time = step_start_time
                        active_notes.clear()

                    for note in step.notes:
                        translated_pitch = self._translate_note(note.pitch, instrument_name)
                        track.append(mido.Message(
                            'note_on',
                            note=translated_pitch,
                            velocity=note.velocity,
                            channel=channel,
                            time=delta
                        ))
                        delta = 0
                        last_event_time = step_start_time
                        active_notes[translated_pitch] = step_start_time
                else:
                    # Rest: turn off any active notes
                    if active_notes:
                        for note_pitch in list(active_notes.keys()):
                            track.append(mido.Message(
                                'note_off',
                                note=note_pitch,
                                velocity=0,
                                channel=channel,
                                time=delta
                            ))
                            delta = 0
                            last_event_time = step_start_time
                        active_notes.clear()
            else:  # sustain mode
                if step.is_tie:
                    # Keep holding notes across ties
                    pass
                else:
                    if active_notes:
                        for note_pitch in list(active_notes):
                            track.append(mido.Message(
                                'note_off',
                                note=note_pitch,
                                velocity=0,
                                channel=channel,
                                time=delta
                            ))
                            delta = 0
                            last_event_time = step_start_time
                        active_notes.clear()

                    if not step.is_rest:
                        for note in step.notes:
                            translated_pitch = self._translate_note(note.pitch, instrument_name)
                            track.append(mido.Message(
                                'note_on',
                                note=translated_pitch,
                                velocity=note.velocity,
                                channel=channel,
                                time=delta
                            ))
                            delta = 0
                            last_event_time = step_start_time
                            active_notes.add(translated_pitch)

        total_steps = len(track_data.steps)
        final_time = self._calculate_swing_time(total_steps)

        # Close out any sustaining notes at the final step boundary
        if self.config.note_mode == 'trigger':
            remaining_notes = list(active_notes.keys())
        else:
            remaining_notes = list(active_notes)

        delta = max(0, final_time - last_event_time)
        for idx, note_pitch in enumerate(remaining_notes):
            track.append(mido.Message(
                'note_off',
                note=note_pitch,
                velocity=0,
                channel=channel,
                time=delta if idx == 0 else 0
            ))
            delta = 0
        if remaining_notes:
            last_event_time = final_time

        active_notes.clear()

        # Ensure the track duration matches the tracker timeline
        end_padding = max(0, final_time - last_event_time)
        track.append(mido.MetaMessage('end_of_track', time=end_padding))

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

    def create_realtime_messages(
        self,
        tracks: Dict[str, InstrumentTrack],
        start_step: int = 0,
        num_steps: int = None,
        include_note_off_at_end: bool = True
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

            # Set program change at t=0 (only if not already sent for this instrument)
            if instrument_name != 'DRUMS' and self.config.send_program_changes:
                if instrument_name not in self._programs_sent:
                    program = self.config.programs.get(instrument_name, 0)
                    messages.append((0.0, mido.Message('program_change', program=program, channel=channel)))
                    self._programs_sent.add(instrument_name)

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
                        translated_pitch = self._translate_note(note.pitch, instrument_name)
                        messages.append((
                            step_time,
                            mido.Message('note_on', note=translated_pitch, velocity=note.velocity, channel=channel)
                        ))
                        active_notes[translated_pitch] = (note.velocity, step_time)

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

        # Optionally schedule final note off to flush tail
        if include_note_off_at_end:
            final_time = 0.0
            for instrument_steps in tracks.values():
                final_time = max(final_time, len(instrument_steps.steps))
            if final_time > 0:
                beats_per_second = self.tempo / 60.0
                steps_per_beat = 4
                time_per_step = 1.0 / (beats_per_second * steps_per_beat)
                tail_time = self._calculate_swing_time_seconds(int(final_time), time_per_step)
                for instrument_name, track_data in tracks.items():
                    channel = self.config.channels.get(instrument_name, 0)
                    # CC 123 is the General MIDI "All Notes Off" controller
                    messages.append((
                        tail_time,
                        mido.Message('control_change', control=123, value=0, channel=channel)
                    ))

        # Sort by time
        messages.sort(key=lambda x: (x[0], getattr(x[1], 'type', '')))
        return messages


def tracker_to_midi_file(
    tracks: Dict[str, InstrumentTrack],
    runtime_config: RuntimeConfig,
    tempo: Optional[int] = None
) -> mido.MidiFile:
    """
    Convenience function: Convert tracker data to MIDI file

    MIDI files are created with GM-standard drum notes (no translation)
    so they play correctly on any GM-compatible device/soundfont.

    Args:
        tracks: Dict mapping instrument name to InstrumentTrack
        runtime_config: Immutable runtime configuration.
        tempo: BPM override (defaults to runtime_config.tempo)
    Returns:
        mido.MidiFile
    """
    # Disable drum translation for MIDI files - use GM standard
    converter = MIDIConverter(runtime_config, tempo=tempo, translate_drums=False)
    return converter.create_midi_file(tracks)
