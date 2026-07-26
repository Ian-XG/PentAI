# PentAI

A terminal AI agent that helps you learn ethical hacking by planning and running commands with you, one confirmed step at a time.

## Ethical use

PentAI is built for authorized security testing and hands-on learning only: use it against systems you own or have explicit written permission to test (your own lab, a CTF, a client engagement with signed scope). PentAI is open source and dual-use software - it does not know or enforce what you are authorized to touch. You are solely responsible for how you use it and for complying with the law in your jurisdiction. The built-in scope list and confirmation prompts are safety rails, not a substitute for authorization.

## Install

Requires Python 3.11+.

```bash
git clone <this-repo>
cd pentai
pip install -e ".[dev]"
```

## Run

```bash
pentai
```

This prints the boot banner, then drops you into a prompt:

```
root@pentai:~#
```

Type natural language and the agent will plan and (with your confirmation) run shell commands. Type `/help` to see available commands, `/quit` to exit.

Use `--no-fx` to skip the boot animation and print a plain banner (useful for scripts, low-color terminals, or piping input):

```bash
pentai --no-fx
```

## Provider setup

PentAI is BYOK (bring your own key) and works with:

- **Anthropic** (native Messages API) - set `ANTHROPIC_API_KEY`
- **Any OpenAI-compatible endpoint** - OpenAI itself, Ollama, Groq, OpenRouter, etc. - set `OPENAI_API_KEY` (or a custom env var, see below)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
pentai
```

By default PentAI is configured with an `anthropic` provider (`claude-opus-4`) and an `openai` provider (`gpt-4o` against the official OpenAI API), and reads the matching API key from the environment automatically.

`pentai/config.example.yaml` documents the full config schema used by `pentai.config.load_config` / `Config` / `ProviderConfig`, including how to point at other OpenAI-compatible backends such as Ollama or Groq and how to override which environment variable a provider reads its key from with the per-provider `api_key_env` field:

```yaml
# ~/.pentai/config.yaml  (copy from config.example.yaml)
active: anthropic
palette: green
fx: true
scope: []
providers:
  anthropic:
    kind: anthropic
    model: claude-opus-4
  openai:
    kind: openai_compat
    model: gpt-4o
    base_url: https://api.openai.com/v1
  ollama:
    kind: openai_compat
    model: llama3
    base_url: http://localhost:11434/v1
```

Each provider entry sets `kind` (`anthropic` or `openai_compat`), `model`, an optional `base_url` (for `openai_compat` providers pointing at Ollama, Groq, OpenRouter, etc.), and an optional `api_key_env` naming the environment variable to read the key from (falls back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` by provider name).

## Slash commands

- `/scope add <target>` - add a host, IP, CIDR, or glob pattern to the authorized-scope list
- `/scope list` - show the current scope list
- `/help` - list available commands
- `/quit` - exit PentAI

Anything else you type is sent to the agent as a natural-language request. When the agent wants to run a shell command, you are prompted to confirm; if the command touches a target outside your `/scope` list, you get an extra out-of-scope warning before you can approve it.

## Playbooks

PentAI ships four methodology playbooks in `pentai/skills/` that the agent can load as needed during a session:

- `recon.md`
- `web-owasp.md`
- `priv-esc.md`
- `reporting.md`

## License

MIT - see [LICENSE](LICENSE).
