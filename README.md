# CodeAtlas

[![Python Code Quality](https://github.com/lucanegrianalyst/CodeAtlas/actions/workflows/ci.yml/badge.svg)](https://github.com/lucanegrianalyst/CodeAtlas/actions/workflows/ci.yml)

Un tool CLI avanzato sviluppato in Python per l'inventario, l'analisi statica e la generazione di report (JSON/Markdown/TXT) di progetti software complessi. 

CodeAtlas è progettato per estrarre una vista strutturata del codice e dell'ambiente (runtime, database, API, flussi dati) al fine di fornire contesto strutturato e documentazione tecnica, utile anche per l'integrazione con sistemi AI (LLM).

## 🏗️ Architettura e Caratteristiche

Il sistema si basa su un orchestratore centrale che esegue in sequenza **15 analyzer** indipendenti. L'architettura combina:
- **Analisi Statica (AST):** Parsing del codice per estrarre import, definizioni, chiamate, endpoint API e flussi logici.
- **Analisi dei Dati:** Ispezione di database SQLite (in modalità read-only), generazione di schema, indici e controllo dell'integrità.
- **Analisi di Sistema (Windows):** Raccolta opzionale di snapshot su processi in esecuzione, porte TCP e risorse hardware tramite PowerShell.
- **Generazione di Report:** Aggregazione dei dati in mappe JSON intermedie e generazione di report finali in Markdown per sviluppatori e sistemi AI.

## 🛠️ Tecnologie Utilizzate

- **Linguaggio:** Python 3.11+ (nessuna dipendenza esterna `pip` richiesta, solo standard library)
- **Moduli Core:** `ast`, `sqlite3`, `subprocess`, `pathlib`, `json`
- **Ambiente:** Progettato per Windows (per le fasi di runtime/hardware), con fasi di analisi statica portabili.

## ⚙️ Come funziona (Workflow)

1. **Inventario:** Mappatura dei file, hashing, individuazione di entrypoint e backup.
2. **Analisi Profonda:** Scansione di configurazioni, rilevamento segreti (redatti), estrazione endpoint API, costruzione del call graph.
3. **Sintesi e Handoff:** Aggregazione incrociata dei dati per generare un "Project Functional Manual" e un contesto pronto per essere letto da un LLM.

## ⚠️ Stato del Progetto e Limitazioni Note

*Trasparenza sullo stato di sviluppo:*
- Il progetto è un **prototipo funzionante** ed è in fase di refactoring architetturale.
- **Test:** Attualmente non è presente una suite di test automatizzati per tutti gli analyzer (è in fase di sviluppo).
- **Analisi Euristica:** Trattandosi di analisi statica, i risultati (come i call graph o i flussi dati) rappresentano inferenze sintattiche e non tracce di runtime.
- **Root di scansione:** È richiesta la corretta configurazione della directory di root nel file `project_context.py` per evitare scansioni al di fuori del progetto target.

## 🎯 Obiettivi Futuri

- Implementazione di una suite di test unitari e di integrazione portabile.
- Miglioramento della modularità (riduzione della complessità ciclomatica di alcuni analyzer).
- Rilascio di una CLI per la configurazione dinamica della root e dei parametri di output.
