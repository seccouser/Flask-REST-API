# Configuration File

Copy `config.example.json` to `config.json` and adjust settings as needed.

## Configuration Options

- `upload_folder`: Directory for uploaded files (default: "uploads")
- `max_content_length`: Maximum file size in bytes (default: 104857600 = 100 MB)
- `allowed_extensions`: List of allowed file extensions (empty = all allowed)
- `host`: Server bind address (default: "0.0.0.0")
- `port`: Server port (default: 5000)
- `debug`: Enable debug mode (default: false)
- `keyboard_emulation.enabled`: Enable keyboard emulation (default: true)
- `keyboard_emulation.default_delay`: Default delay between keypresses in seconds (default: 0.1)
- `logging.level`: Log level (INFO, DEBUG, WARNING, ERROR)
- `logging.format`: Log message format

## Example

```json
{
  "upload_folder": "uploads",
  "max_content_length": 104857600,
  "host": "0.0.0.0",
  "port": 5000
}
```
