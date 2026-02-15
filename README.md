# brickstuff

## Rebrickable helpers

### Prerequisites

- Python 3.10+ installed (`python3 --version`)
- A Rebrickable API key from https://rebrickable.com/api/

### CLI

Run the CLI fetcher with an API key in `REBRICKABLE_API_KEY`:

```bash
export REBRICKABLE_API_KEY='your_rebrickable_api_key'
python3 fetch_rebrickable.py lego/parts/3001/
```

Optional query parameters can be repeated with `--param`:

```bash
python3 fetch_rebrickable.py lego/parts/3001/ --param inc_part_details=1
```

### Web lookup

Start a local web page for part number lookups:

```bash
export REBRICKABLE_API_KEY='your_rebrickable_api_key'
python3 web_app.py
```

Then visit `http://localhost:8000` and enter a part number.


### Use a local config file (.env)

Yes. You can place these values in a `.env` file in the project root so you can run `python3 web_app.py` directly.

1. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set your values:
   ```text
   REBRICKABLE_API_KEY='your_rebrickable_api_key'
   REBRICKABLE_SKIP_SSL_VERIFY=0
   ```
3. Run the app:
   ```bash
   python3 web_app.py
   ```

The app and CLI now auto-load `.env` (without overriding variables already exported in your shell).

## Running locally on macOS

From Terminal:

1. Clone and enter the repo:
   ```bash
   git clone <your-repo-url>
   cd brickstuff
   ```
2. Confirm Python 3 is available:
   ```bash
   python3 --version
   ```
3. Set your API key for the current shell:
   ```bash
   export REBRICKABLE_API_KEY='your_rebrickable_api_key'
   ```
4. Run either interface:
   - CLI:
     ```bash
     python3 fetch_rebrickable.py lego/parts/3001/
     ```
   - Web app:
     ```bash
     python3 web_app.py
     ```
5. If using the web app, open `http://localhost:8000` in your browser.

Tip: to persist the key, add the `export REBRICKABLE_API_KEY=...` line to `~/.zshrc` (default macOS shell).

## Troubleshooting SSL certificate errors on macOS

If you see an error like:

```text
CERTIFICATE_VERIFY_FAILED
```

your Python install may not have the macOS certificate bundle configured.

### Recommended fix

Run the certificate installer script that ships with Python.org builds:

```bash
open "/Applications/Python 3.10/Install Certificates.command"
```

(Adjust `3.10` to your installed Python version.)

Then restart your terminal and run the app again.

### Temporary workaround (not recommended for long-term use)

You can bypass SSL verification for this script only:

```bash
export REBRICKABLE_SKIP_SSL_VERIFY=1
python3 web_app.py
```

Use this only as a short-term workaround.
