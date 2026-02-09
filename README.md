# brickstuff

## Rebrickable helpers

### CLI

Run the CLI fetcher with an API key in `REBRICKABLE_API_KEY`:

```bash
python fetch_rebrickable.py lego/parts/3001/
```

### Web lookup

Start a local web page for part number lookups:

```bash
REBRICKABLE_API_KEY=your_key python web_app.py
```

Then visit `http://localhost:8000` and enter a part number.
