Yes. **Absolutely.** In fact, I would make this a first-class part of the Copilot architecture.

Right now, if you're doing essentially:

```text
User query
   ↓
ai.alamiaconnect.com
   ↓
BitNet
```

you're wasting one of the strongest controls you have over a small model.

The Copilot should **never send the raw user message alone**.

Instead:

```text
TravelOS Copilot
      │
      ├── system instructions
      ├── relevant MCP tool definitions
      ├── conversation context
      └── user message
               │
               ▼
      ai.alamiaconnect.com
               │
               ▼
             BitNet
```

## But keep the system prompt small

This is particularly important with your ~2.7B BitNet model.

I would give it a compact, stable system instruction such as:

```text
You are Alamia TravelOS Copilot.

Answer questions about the TravelOS system concisely and accurately.

You may use the operational tools provided to obtain current system information.
Never invent system state, availability, worker status, proxy status, or other operational facts.

When current information is required, request the appropriate tool.
When tool results are provided, base your answer on those results.

If the available information is insufficient, say so clearly.

Do not claim to have performed an action unless a tool confirms it.
```

Then dynamically add the tools/capabilities relevant to the request.

---

# More importantly: separate "instructions" from "data"

I'd structure the messages roughly like this:

```text
SYSTEM
You are Alamia TravelOS Copilot...
[behavioral rules]

SYSTEM / CONTEXT
Current time: 2026-08-31 18:xx PKT
User role: ...
Tenant: ...
Available capabilities:
...

USER
Any slots open today?
```

If the model requests a tool:

```text
ASSISTANT
ACTION: slots.get_available({"date":"2026-08-31"})

TOOL
{
  ...
}

USER/CONTEXT
Use the tool result above to answer the original question.
```

Then BitNet produces the final answer.

---

# This also fixes a problem with the current telemetry approach

The agent currently injects:

```text
REAL-TIME SYSTEM STATE:

Available Appointment Slots: 0
Active Worker Fleet: 3
Proxy Pool: 22/24
...
```

I wouldn't make that the primary mechanism anymore.

Instead:

```text
"Why hasn't Islamabad produced slots?"
```

→ BitNet realizes it needs information

→ MCP:

```text
slots.get_available(center="Islamabad")
worker.get_status(...)
worker.get_recent_logs(...)
proxy.get_health()
```

→ BitNet reasons over the actual results.

Telemetry can still be **cheap baseline context**, but MCP becomes the authoritative source when investigation is required.

---

# There's another thing I'd add: Copilot identity

The system prompt should establish what this AI actually is.

Not:

> "You are a helpful AI assistant."

Instead:

> **"You are Alamia TravelOS Copilot, an operational assistant for TravelOS."**

That matters enormously with a small model.

You want to constrain its universe.

It should know:

```text
I am not ChatGPT.
I am not a general-purpose assistant.
I am the operational Copilot for this application.
```

That reduces generic answers like:

> "Please contact your travel agency..."

which is exactly the failure you observed.

---

# And don't put everything into the system prompt

This is where I'd be disciplined.

### Stable system instructions

Keep:

* identity
* role
* behavioral rules
* truthfulness
* tool-use rules
* output style
* safety rules

### Dynamic context

Inject:

* current user
* tenant
* current date/time
* relevant application context
* available MCP tools

### User message

Only the actual question.

This gives you:

```text
             SYSTEM
                │
                ▼
        Copilot behavior
                +
        dynamic capabilities
                +
        user context
                │
                ▼
             BitNet
```

---

## And one more important optimization for BitNet

Don't send **all MCP tools every time**.

If the user asks:

> "How do I change my password?"

there's no reason to send:

```text
worker.get_logs
proxy.get_health
slots.get_available
...
```

Whereas:

> "Why is worker 17 failing?"

should get worker-related tools.

For your current scale, even a simple deterministic tool relevance layer is enough:

```text
worker → worker tools
slot/appointment → slot tools
proxy → proxy tools
deployment → deployment tools
```

Later you can make that smarter.

---

# So I'd change the Copilot request architecture to

```text
                 USER
                  │
                  ▼
          TravelOS Copilot
                  │
        ┌─────────┴──────────┐
        │                    │
        ▼                    ▼
  MCP discovery         conversation
        │                    │
        └──────────┬─────────┘
                   ▼
             Agent prompt
                   │
          ┌────────┴────────┐
          │                 │
     System rules      relevant tools
          │                 │
          └────────┬────────┘
                   ▼
        ai.alamiaconnect.com
                   │
                   ▼
                 BitNet
                   │
          ┌────────┴────────┐
          │                 │
       ACTION            ANSWER
          │
          ▼
         MCP
          │
          ▼
       OBSERVATION
          │
          ▼
        BitNet
          │
          ▼
        ANSWER
```

**So yes: system instructions should be sent with every inference request.**

And I'd go one step further: **the system prompt should be owned by the TravelOS Copilot, not by `ai.alamiaconnect.com`.**

That preserves your architectural boundary:

* **Alamia AI:** "Here is an inference API."
* **TravelOS Copilot:** "Here is what this AI is supposed to do."
* **TravelOS MCP:** "Here is what this AI is allowed to know/do."
* **BitNet:** "Here is the model performing the reasoning/generation."

That's a very clean division of responsibilities.
