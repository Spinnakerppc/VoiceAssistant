"""
audio_devices.py — Auto-detect PipeWire device IDs by name.
Solves the "IDs change on reboot" problem.
"""
import subprocess
import re

def get_node_id(name_fragment: str, node_type: str = "sink") -> str:
    """
    Find a PipeWire node ID by partial name match.
    node_type: 'sink' (output) or 'source' (input)
    """
    result = subprocess.run(
        ["wpctl", "status"], capture_output=True, text=True
    )

    section = "Sinks" if node_type == "sink" else "Sources"
    in_section = False

    for line in result.stdout.splitlines():
        if section in line:
            in_section = True
            continue
        if in_section:
            # Stop at next section header
            if "──" in line and section not in line:
                if any(s in line for s in ["Sinks","Sources","Filters","Streams","Devices","Settings"]):
                    in_section = False
                    continue
            # Match lines like:  │      78. Jabra SPEAK 410 Analog Stereo
            match = re.search(r'(\d+)\.\s+(.+?)(?:\s+\[|$)', line)
            if match:
                node_id = match.group(1)
                node_name = match.group(2).strip()
                if name_fragment.lower() in node_name.lower():
                    return node_id

    raise RuntimeError(f"Could not find {node_type} matching '{name_fragment}'")


def get_jabra_sink() -> str:
    """Return Jabra Speak output node ID."""
    return get_node_id("Jabra SPEAK 410 Analog", "sink")


def get_fifine_source() -> str:
    """Return Fifine mic input node ID."""
    return get_node_id("fifine Microphone Mono", "source")


if __name__ == "__main__":
    print(f"Jabra sink  : {get_jabra_sink()}")
    print(f"Fifine source: {get_fifine_source()}")
