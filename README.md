# somfy-rts-hub

somfy-rts-hub is a small package that communicates with
ESP's which have [somfy-rts-esp](https://github.com/LukasHirsch99/ESP-Somfy) installed.

## Features
- Get covers from hub
- Control covers (up, down, stop)
- Add, rename and remove covers

## Installation

You can install the package via **PyPI** or from **source**.

### Install from PyPI

```bash
pip install somfy-rts-hub
```

### Install from source

```bash
git clone https://github.com/LukasHirsch99/somfy-rts-hub
cd somfy-rts-hub
pip install .
```

## Usage

After installation you can use `somfy-rts-cover` to control and manage your covers.

### Example

```python
from somfyrtshub import Hub

# Initialize the hub
hub = Hub(HOST, PORT)
# Connects to the hub and returns all safed covers
covers = hub.getAllCovers()

# Open all covers
for c in covers:
    c.open()
```
