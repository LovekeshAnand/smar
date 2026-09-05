# SMAR — Voice-First Memory Assistant for Kirana & Warehouse Workers

## Updated Architecture & Design Document (v2)

---

## 0. What changed from v1, and why

The original SMAR architecture (`memory-driven-voice-automation-architecture.md`) had a voice interface, a cognitive context layer (knowledge graph + vector store), and a local LLM reasoning layer — all of which are staying exactly as they were. What v1 *also* had, on its right-hand side, was an **automation layer**: a universal connector that reached out to Gmail, WhatsApp, and other external apps, normalized their data, and fed it into the vector store.

That automation branch is being removed. In its place is a **smart data layer** purpose-built for a completely different problem: giving an illiterate, Hindi-speaking kirana store or warehouse worker instant voice access to a large, structured inventory dataset — on the order of **1 lakh (100,000) data points** — without making them type, read, or touch a screen at all.

This is not a small tweak. It changes what the system's memory is *for*. In v1, memory grew from conversations with external apps. In v2, memory grows from **usage of a large existing dataset** — the KG becomes a cache that gets warmer the more the system is used, sitting in front of a cold, bulk-loaded database. Everything below explains that shift and the engineering decisions it forced.

---

## 1. Overview

SMAR v2 is a **voice-first, Hindi-native inventory assistant** built around three ideas working together:

1. A **persistent, self-updating Context Layer** (knowledge graph + vector store) that does not start over every session — this is unchanged from v1 and remains the system's long-term memory.
2. A **Smart Data Layer** that sits between the reasoning loop and a large (~1 lakh row) structured database, resolving vague spoken language into exact records, checking the KG before ever touching the database, and writing back what it learns so repeat questions get faster over time.
3. A **fully voice, zero-literacy interaction model** — no text is ever required from the user, and every consequential answer is confirmed back verbally before being trusted.

The target user is a kirana store owner, a warehouse floor worker, or similar — someone who knows their stock and their business intimately, but cannot or does not want to read a screen, type in an app, or navigate a menu. The system should feel less like "using software" and more like asking a colleague who remembers everything.

---

## 2. The Core Problem (restated for v2)

Two problems compound here, not one:

- **The literacy/accessibility problem.** Every existing inventory or ERP tool assumes a literate user who can read labels, type search terms, and navigate screens. That excludes a huge population of the actual people who run kirana stores and warehouses day to day. Voice is not a nice-to-have interface option here — it is the *only* viable interface.
- **The scale/freshness problem.** A real kirana store or warehouse doesn't have 200 items — it can easily have tens of thousands of SKUs and, across a transaction history, well over 1 lakh individual data points. Any system that tries to reason over all of that by stuffing it into an LLM prompt, or by re-scanning it on every voice query, will be too slow to feel conversational and too expensive to run locally.

SMAR v2's answer to both: voice as the only interface, and a **knowledge graph that behaves like a cache** — small and fast for what's actually been asked about, backed by a large indexed database for everything else.

---

## 3. Core Architecture & Data Flow

```
[User: kirana/warehouse worker] <--- Spoken Hindi ---> [Gnani STT / TTS]
                                                              |
                                                           (Text)
                                                              v
        +--------------------------------------------------------+
        |                Cognitive Context Layer                 |
        |   (UNCHANGED FROM v1 — long-term memory)                |
        |                                                        |
        |  +----------------------+   +-----------------------+  |
        |  |  Knowledge Graph     |   |     Vector Store      |  |
        |  |  (relational facts)  |   |  (semantic memories)  |  |
        |  +----------+-----------+   +-----------+-----------+  |
        +-------------+---------------------------+--------------+
                      |                            |
                      +-------------+--------------+
                                    v
                       Hybrid RAG Query / Dynamic Prompt
                                    |
                                    v
        +--------------------------------------------------------+
        |            Local LLM Reasoning Engine (Epsilon)        |
        |             (Qwen2.5-Coder 7B via llama-server)         |
        +----------------------------+-----------------------------+
                                     |
                                     v
                              [Work Intent]
                                     |
                                     v
        +--------------------------------------------------------+
        |                  SMART DATA LAYER  (NEW — replaces      |
        |                  the v1 automation/connector branch)   |
        |                                                        |
        |  1. Entity Resolution                                  |
        |     (spoken Hindi term -> canonical item)              |
        |                    |                                  |
        |                    v                                  |
        |  2. KG Cache Lookup ---- hit ----> answer from KG       |
        |                    |                                  |
        |                   miss                                |
        |                    v                                  |
        |  3. Search Bulk DB (1 lakh rows, indexed, blocked)     |
        |                    |                                  |
        |                    v                                  |
        |  4. Upsert result into KG (writes back to cache)       |
        +----------------------------+-----------------------------+
                                     |
                                     v
                      [Synthesized Spoken Reply — with
                       confirm-back for consequential facts]
                                     |
                                     v
                           [Gnani Timbre TTS] --> Speaker
```

The loop from User through Gnani, through the Context Layer, through the LLM, is identical to v1. What's new sits between "Work Intent" and the spoken reply: the Smart Data Layer.

---

## 4. Component Breakdown

### 4.1 Voice Interface Layer (unchanged from v1)

- **STT (Gnani Prisma v2.5)**: streaming, low-latency, supports `hi-IN` and multilingual code-switching (a worker may say a Hindi sentence with an English brand name in the middle — "panch kilo Tata Salt hai kya" — and this needs to transcribe cleanly).
- **TTS (Gnani Timbre v2.5)**: expressive neural synthesis over SSE. Responses should be short, direct sentences — this is a spoken interface for someone who cannot glance back at a transcript to check they heard correctly, so brevity and clarity matter more than exhaustive detail.

### 4.2 Cognitive Context Layer (unchanged from v1)

- **Knowledge Graph**: relational triples (`item, attribute, value`) with case-insensitive entity resolution and confidence scores. This is where cached facts about specific items live once they've been looked up at least once.
- **Vector Store**: subword hashing vectorizer, upsert-by-similarity, for semantic recall of things that don't fit neatly into triples (e.g. a worker's own phrasing of a past request).
- These two together are still the system's only long-term memory. The Smart Data Layer writes into this same KG — it does not maintain a separate memory of its own.

### 4.3 Smart Data Layer (new — this is the core of v2)

This is the component that replaces the automation/connector branch entirely, and it has four responsibilities:

**a. Entity resolution.** A worker will never say the exact item name as it's stored in the database. They'll say a colloquial, regional, or abbreviated term. This step maps what was actually said to a canonical item record. It reuses the same fuzzy-matching and blocking techniques already designed for material-code standardization in a separate project — partition candidates by category/attribute first, then run similarity scoring within that partition, rather than comparing against all 1 lakh rows every time.

**b. KG cache lookup.** Before touching the bulk database at all, check whether this item (or this exact question about this item) has already been resolved and cached in the KG. If yes, answer immediately — no database round-trip, no re-computation.

**c. Bulk database search (on cache miss only).** The 1 lakh rows live in a properly indexed database — not a linear scan. Indexed lookups by canonical item code are near-instant; fuzzy text search (for when entity resolution wasn't fully confident) uses trigram or similar indexing rather than scanning every row.

**d. Upsert into KG.** Whatever was just fetched from the bulk database gets written into the KG as a triple, so the *next* time anyone asks about that item, it's a cache hit. This is the mechanism that makes the system get faster the more it's used — memory here is a function of usage, not a fixed dataset dump.

### 4.4 Reasoning Layer (unchanged from v1)

- **Local Qwen 7B Instruct**, zero external API cost, fully private, no network dependency — this matters doubly here since kirana stores and warehouses are often in low-connectivity areas.
- Dynamic prompt composition still happens per turn, now including whatever the Smart Data Layer just resolved (a KG hit or a freshly upserted fact) alongside the usual conversational context.

---

## 5. The Clever Engineering (why this isn't just "a KG with extra steps")

This section is the part worth walking a judge or reviewer through directly, because each decision here solves a specific failure mode that a naive version of this system would hit.

### 5.1 Two ingestion paths, not one

v1 had a single ingestion path: the local LLM reads a conversation turn and extracts facts into the KG. That's fine for a few dozen or hundred facts accumulated in conversation. It is **not** fine for loading 1 lakh rows of structured data — running an LLM extraction pass over 100,000 rows would take hours and add nothing, since the data already arrives structured (a CSV or database export of SKUs, quantities, prices).

So v2 splits ingestion into two paths that both write into the same KG:

- **Bulk path**: a deterministic loader maps structured rows directly into KG triples and vector embeddings, no LLM involved. This is how the 1 lakh points get in before anyone's spoken a word to the system.
- **Conversational path**: the original v1 LLM-based extractor, unchanged, for facts a worker states out loud during a session ("aaj pachaas bag cement aaya").

The reason this matters for the pitch: it's a deliberate, explainable architectural choice, not an oversight — the system uses the right ingestion mechanism for the right kind of data, instead of forcing everything through the expensive path.

### 5.2 The KG as a cache, not a copy

The naive version of "put 1 lakh data points in a knowledge graph" is to embed and triple-ify all 100,000 rows upfront. That's wasteful: most items in a large inventory are asked about rarely, if ever, and a KG that size becomes slow to query and expensive to maintain for no benefit.

Instead, the KG starts near-empty (aside from anything explicitly pre-seeded) and grows **only for what's actually been asked about** — a classic cache-aside pattern, applied to a knowledge graph instead of a key-value store. The bulk database remains the full source of truth; the KG is the fast, warm subset that's proven useful in practice. This is also why repeat questions get visibly faster over a demo or a real shift — the second time anyone asks about an item, there's no database round-trip at all.

### 5.3 Volatility-aware caching

Not every field in a stock record behaves the same way. An item's name, category, and unit of measure basically never change. Its stock quantity changes constantly. Caching a quantity in the KG and serving it forever would mean the system confidently gives a wrong answer the moment stock moves.

So fields are split by volatility:
- **Static fields** (name, category, unit, standard attributes) — cached in the KG indefinitely, since they're safe to reuse.
- **Volatile fields** (quantity on hand, current price) — always read live from the bulk database, never served from a stale cache, even if the item itself is otherwise a cache hit.

This is a small rule with an outsized effect on trust: it means the system can legitimately claim "the KG makes this fast" while never being caught giving an obviously wrong stock count.

### 5.4 Entity resolution reuses a proven matching strategy

Spoken, colloquial, regional-language item references are messy in a way that exact-match lookups can't handle. Rather than inventing a new fuzzy-matching approach from scratch, this layer reuses the blocking-plus-scoring strategy already worked out for a separate material-code standardization problem: partition candidates by a coarse attribute (category, unit) before running any similarity comparison, so the system is never comparing a spoken phrase against all 1 lakh rows — only against the plausible subset. This is what keeps entity resolution fast even as the underlying dataset scales.

### 5.5 Voice-first design for zero literacy, not just Hindi language

Supporting Hindi is a language problem. Supporting an *illiterate* user is a different, harder problem: there is no fallback to "just read the screen if you're not sure." Two consequences follow:

- **No text surfaces anywhere in the interaction.** Not a confirmation screen, not a menu, not a "did you mean" list — everything that would normally be shown as text has to be spoken instead.
- **Consequential facts get a spoken confirm-back.** Before acting on or reporting anything that matters (a quantity, a price, a transaction), the system repeats it back in speech — "aapne kaha panch bag, sahi hai?" — because the one failure mode this user genuinely cannot self-correct for is a misheard number, and there's no way for them to visually double-check a transcript.

### 5.6 Fully local and offline-capable

The reasoning layer runs a local, quantized model with no external API dependency. This isn't just a cost or privacy decision (though it is both of those) — kirana stores and warehouses are frequently in areas with unreliable connectivity, and a system that requires a live cloud connection to answer "how much rice is left" defeats its own purpose.

---

## 6. End-to-End Spoken Turn Flow (v2)

1. **Worker speaks** in Hindi (or code-switched Hindi/English) — captured as 16kHz mono audio.
2. **STT transcription** via Gnani, returning text.
3. **Context retrieval**: as in v1, the Context Layer is queried for relevant KG triples and vector matches for conversational continuity.
4. **Work intent extraction**: the LLM identifies what's actually being asked (a stock check, a price query, a restock log, etc.) and what item is being referred to.
5. **Entity resolution**: the spoken item reference is mapped to a canonical item — checking the KG's own resolution cache first, falling back to blocked fuzzy matching against the bulk DB's item list if needed.
6. **KG cache lookup**: for that canonical item, check whether the KG already holds what's needed.
   - **Cache hit** on all needed fields (respecting the volatility split in 5.3) → answer immediately.
   - **Cache miss**, or a volatile field is involved → query the bulk database directly (indexed lookup, not a scan).
7. **Upsert**: any newly-fetched static fields get written into the KG for next time. Volatile fields are used for this answer but not cached.
8. **LLM composes the spoken reply**, including a confirm-back for anything consequential.
9. **TTS synthesis and playback** via Gnani Timbre.
10. **Background**: as in v1, the conversational fact extractor still runs on the turn to capture anything the worker stated that wasn't itself a database lookup (e.g. "yeh item ab yahan rakhna hai" — a placement note, not a stock fact).

---

## 7. What You Need to Build (in order)

This is the practical build sequence, expanded from the architecture above:

1. **Decide and source the 1 lakh dataset.** SKU master data, transaction ledger, or both — this decides your schema. If no real dataset is available, generate a realistic synthetic one (item names in Hindi/English, categories, units, quantities, prices) rather than guessing at scale with a handful of rows.
2. **Build the bulk-ingest pipeline**, entirely separate from the LLM-based conversational extractor. This is a deterministic script: read the tabular data, write KG triples and vector embeddings directly, no model in the loop.
3. **Index the bulk database properly** before querying it at scale: an index on canonical item code/ID, plus fuzzy/trigram-style indexing on item name text for cold entity-resolution search. Add blocking (partition by category or unit) so similarity comparisons never run against the full 1 lakh rows.
4. **Implement entity resolution** as its own step, distinct from the KG cache lookup — it needs to handle regional/colloquial phrasing before anything can be looked up at all.
5. **Implement the KG cache lookup and upsert logic**, respecting the static/volatile field split from section 5.3.
6. **Design the voice UX around illiteracy**: no text fallback anywhere, spoken confirm-back for consequential answers.
7. **Stress-test the full loop** (voice in → resolution → KG/DB → LLM → voice out) against the full loaded dataset on the actual demo hardware, not just a small sample.
8. **Script the demo** to make the caching behavior visible: start with a near-empty KG, ask a few different questions to show it growing, then repeat one question to visibly show the second answer coming back instantly with no database round-trip.

---

## 8. Summary: What Makes This Defensible to a Judge

If asked "why is this hard, and why is your solution actually clever," the answer is not "we used a knowledge graph and a vector store" — that's just infrastructure. The actual engineering claims are:

- We deliberately use **two different ingestion mechanisms** for two different kinds of data, instead of forcing bulk structured data through an expensive LLM extraction path meant for conversation.
- We treat the **knowledge graph as a cache, not a copy** of the full dataset — it grows in proportion to real usage, not in proportion to dataset size, which is why the system stays fast without needing to embed or reason over all 100,000 rows on every query.
- We explicitly separate **static and volatile fields**, because caching stock quantities the same way as item names would produce confidently wrong answers, and a system that's fast but wrong isn't actually useful.
- We reuse a **blocking-based entity resolution strategy** for messy spoken input, rather than either exact-matching (which fails on colloquial speech) or brute-force fuzzy matching (which doesn't scale to 1 lakh rows).
- We designed for **zero literacy, not just a different language** — every interaction assumes the user cannot read a screen to self-correct, which is a stricter and different constraint than just localizing text to Hindi.

Together, these are what let the system credibly claim it works "at 1 lakh data points" and not just "with a 1 lakh number in a slide."
