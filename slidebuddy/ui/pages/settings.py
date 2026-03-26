import streamlit as st

from slidebuddy.config.defaults import (
    LANGUAGES,
    TEXT_LENGTHS,
    get_available_template_types,
    get_template_labels,
    load_preferences,
    save_preferences,
)
from slidebuddy.llm.prompt_assembler import PROMPT_PHASES, get_default_prompt_text
from slidebuddy.llm.router import clear_llm_cache, clear_models_cache, get_provider_models


def render_settings():
    st.header("Einstellungen")

    prefs = load_preferences()

    tabs = st.tabs(["API-Keys", "Modelle", "Generierung", "RAG", "Prompts", "Praeferenzen"])

    with tabs[0]:
        _render_api_keys(prefs)

    with tabs[1]:
        _render_models(prefs)

    with tabs[2]:
        _render_generation_strategy(prefs)

    with tabs[3]:
        _render_rag_settings(prefs)

    with tabs[4]:
        _render_prompt_editor(prefs)

    with tabs[5]:
        _render_preferences(prefs)


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

def _render_api_keys(prefs: dict):
    api_keys = prefs.get("api_keys", {})

    with st.form("api_keys_form"):
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=api_keys.get("anthropic", ""),
            type="password",
            help="Fuer Claude-Modelle",
        )
        openai_key = st.text_input(
            "OpenAI API Key",
            value=api_keys.get("openai", ""),
            type="password",
            help="Fuer GPT-Modelle und Embeddings",
        )
        google_key = st.text_input(
            "Google AI API Key",
            value=api_keys.get("google", ""),
            type="password",
            help="Fuer Gemini-Modelle",
        )

        if st.form_submit_button("API-Keys speichern"):
            prefs["api_keys"] = {
                "anthropic": anthropic_key,
                "openai": openai_key,
                "google": google_key,
            }
            save_preferences(prefs)
            clear_llm_cache()
            clear_models_cache()  # Re-fetch models with new keys
            st.success("API-Keys gespeichert!")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _render_models(prefs: dict):
    provider_models = get_provider_models()
    all_models = []
    for models in provider_models.values():
        all_models.extend(models)

    default_models = prefs.get("default_models", {})

    with st.form("models_form"):
        planning_model = st.selectbox(
            "Planung (Kapitel + Sektionen)",
            all_models,
            index=all_models.index(default_models.get("planning", all_models[0])) if default_models.get("planning") in all_models else 0,
        )
        generation_model = st.selectbox(
            "Generierung (Slides)",
            all_models,
            index=all_models.index(default_models.get("generation", all_models[0])) if default_models.get("generation") in all_models else 0,
        )
        embedding_model = st.selectbox(
            "Embeddings",
            ["text-embedding-3-small", "text-embedding-3-large"],
            index=0,
        )

        if st.form_submit_button("Modelle speichern"):
            prefs["default_models"] = {
                "planning": planning_model,
                "generation": generation_model,
                "embedding": embedding_model,
            }
            save_preferences(prefs)
            clear_llm_cache()
            st.success("Modelle gespeichert!")


# ---------------------------------------------------------------------------
# Generation Strategy
# ---------------------------------------------------------------------------

def _render_generation_strategy(prefs: dict):
    st.subheader("Batch-Generierung")

    batch_size = st.slider(
        "Batch-Groesse (Folien pro LLM-Call)",
        min_value=1,
        max_value=8,
        value=prefs.get("batch_size", 4),
        key="settings_batch_size",
    )
    st.caption("Mehrere Folien werden in einem LLM-Call zusammen generiert. Guter Kompromiss aus Geschwindigkeit und Kohaerenz.")

    if st.button("Speichern", key="save_strategy"):
        prefs["batch_size"] = batch_size
        save_preferences(prefs)
        st.success("Batch-Groesse gespeichert!")

    st.divider()
    st.subheader("Prompt-Debug-Modus")
    debug_on = st.toggle(
        "Debug-Logging aktivieren",
        value=prefs.get("debug_prompts", False),
        help="Loggt jeden LLM-Call (Prompts, Chunks, Antworten, Tokens) in data/prompt_debug.jsonl",
    )
    if debug_on != prefs.get("debug_prompts", False):
        prefs["debug_prompts"] = debug_on
        save_preferences(prefs)
        st.success("Debug-Modus " + ("aktiviert" if debug_on else "deaktiviert"))

    if debug_on:
        from slidebuddy.llm.prompt_logger import get_log_summary, clear_log, LOG_PATH
        summary = get_log_summary()
        if summary["total_calls"] > 0:
            st.caption(f"Log: {summary['total_calls']} Calls | ~{summary['total_input_tokens']:,} Input-Tokens | ~{summary['total_output_tokens']:,} Output-Tokens | {summary['total_duration_s']}s")
            for phase, stats in summary.get("by_phase", {}).items():
                st.caption(f"  {phase}: {stats['calls']}x | ~{stats['input_tokens']:,} in | ~{stats['output_tokens']:,} out | {round(stats['duration_s'],1)}s")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Log loeschen", key="clear_debug_log"):
                    clear_log()
                    st.rerun()
            with col2:
                if LOG_PATH.exists():
                    st.download_button(
                        "Log herunterladen",
                        LOG_PATH.read_bytes(),
                        file_name="prompt_debug.jsonl",
                        mime="application/jsonl",
                        key="download_debug_log",
                    )
        else:
            st.caption("Noch keine Calls geloggt. Starte eine Generierung.")


# ---------------------------------------------------------------------------
# RAG Settings
# ---------------------------------------------------------------------------

def _render_rag_settings(prefs: dict):
    rag = prefs.get("rag", {})

    with st.form("rag_form"):
        st.subheader("Retrieval (Quellensuche)")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Planung (Kapitel + Sektionen)**")
            n_sources_planning = st.number_input(
                "Quell-Chunks pro Suche",
                min_value=1, max_value=20,
                value=rag.get("n_sources_planning", 5),
                help="Anzahl der Quell-Chunks bei der Sektionsplanung",
            )
            n_global_planning = st.number_input(
                "Globale Slides pro Suche",
                min_value=0, max_value=10,
                value=rag.get("n_global_planning", 3),
                help="Anzahl wiederverwendbarer Slides aus frueheren Projekten",
            )
        with col2:
            st.markdown("**Generierung (Slide-Erstellung)**")
            n_sources_generation = st.number_input(
                "Quell-Chunks pro Suche ",
                min_value=1, max_value=20,
                value=rag.get("n_sources_generation", 3),
                help="Anzahl der Quell-Chunks bei der Slide-Generierung",
            )
            n_global_generation = st.number_input(
                "Globale Slides pro Suche ",
                min_value=0, max_value=10,
                value=rag.get("n_global_generation", 2),
                help="Anzahl wiederverwendbarer Slides bei der Generierung",
            )

        st.divider()
        st.subheader("Auto-Chunk-Zuordnung")
        n_chunks_per_slide = st.number_input(
            "Chunks pro Folie (nach Sektionsplanung)",
            min_value=1, max_value=10,
            value=rag.get("n_chunks_per_slide", 3),
            help="Wie viele Chunks automatisch pro Folie zugeordnet werden",
        )

        st.divider()
        st.subheader("Kontext-Limit")
        max_context_chars = st.number_input(
            "Max. Zeichen fuer RAG-Kontext im Prompt",
            min_value=1000, max_value=30000, step=500,
            value=rag.get("max_context_chars", 6000),
            help="Zeichenbudget fuer Quellkontext im LLM-Prompt. Groessere Werte = mehr Kontext, aber mehr Tokens.",
        )

        st.divider()
        st.subheader("Chunking (Textaufteilung)")
        col3, col4 = st.columns(2)
        with col3:
            chunk_size = st.number_input(
                "Chunk-Groesse (Tokens)",
                min_value=100, max_value=2000, step=50,
                value=rag.get("chunk_size", 500),
                help="Ziel-Groesse pro Chunk in Tokens (~4 Zeichen/Token). Aenderung wirkt nur bei neuem Upload.",
            )
        with col4:
            chunk_overlap = st.number_input(
                "Chunk-Ueberlappung (Tokens)",
                min_value=0, max_value=500, step=10,
                value=rag.get("chunk_overlap", 50),
                help="Ueberlappung zwischen Chunks. Aenderung wirkt nur bei neuem Upload.",
            )

        if st.form_submit_button("RAG-Einstellungen speichern"):
            prefs["rag"] = {
                "n_sources_planning": n_sources_planning,
                "n_global_planning": n_global_planning,
                "n_sources_generation": n_sources_generation,
                "n_global_generation": n_global_generation,
                "n_chunks_per_slide": n_chunks_per_slide,
                "max_context_chars": max_context_chars,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }
            save_preferences(prefs)
            st.success("RAG-Einstellungen gespeichert!")


# ---------------------------------------------------------------------------
# Prompt Editor
# ---------------------------------------------------------------------------

# Phases that are editable in the UI (grouped for display)
_EDITABLE_PHASES = {
    "Basis": ["role", "quality_criteria"],
    "Planung": ["chapter_planning", "section_planning"],
    "Generierung": ["slide_generation"],
}

_PHASE_LABELS = {
    "role": "Rolle",
    "quality_criteria": "Qualitaetskriterien",
    "chapter_planning": "Kapitelplanung",
    "section_planning": "Sektionsplanung",
    "slide_generation": "Slide-Generierung (inkl. Batch + Stil + Format)",
}


def _render_prompt_editor(prefs: dict):
    st.subheader("Prompt-Editor")
    st.caption("Bearbeite die Prompts fuer jede Phase. Custom-Prompts koennen gespeichert und geloescht werden. Default-Prompts sind nicht loeschbar.")

    custom_prompts = prefs.get("custom_prompts", {})
    active_prompts = prefs.get("active_prompts", {})

    # Phase selection
    group = st.selectbox(
        "Kategorie",
        list(_EDITABLE_PHASES.keys()),
        key="prompt_group",
    )

    phases = _EDITABLE_PHASES[group]
    phase_key = st.selectbox(
        "Prompt",
        phases,
        format_func=lambda k: _PHASE_LABELS.get(k, k),
        key="prompt_phase",
    )

    # Active prompt source selector
    # Options: "default" + all custom prompts for this phase
    matching_custom = {
        name: p for name, p in custom_prompts.items()
        if p.get("phase") == phase_key
    }

    source_options = ["default"] + list(matching_custom.keys())
    active_source = active_prompts.get(phase_key, "default")
    if active_source not in source_options:
        active_source = "default"

    source_idx = source_options.index(active_source)

    selected_source = st.selectbox(
        "Aktiver Prompt",
        source_options,
        index=source_idx,
        format_func=lambda s: "Default (nicht loeschbar)" if s == "default" else s,
        key=f"prompt_source_{phase_key}",
    )

    # Apply active prompt change
    if selected_source != active_source:
        if selected_source == "default":
            active_prompts.pop(phase_key, None)
        else:
            active_prompts[phase_key] = selected_source
        prefs["active_prompts"] = active_prompts
        save_preferences(prefs)
        st.rerun()

    # Display current prompt text
    if selected_source == "default":
        current_text = get_default_prompt_text(phase_key)
        is_default = True
    else:
        current_text = matching_custom[selected_source].get("text", "")
        is_default = False

    edited_text = st.text_area(
        "Prompt-Text",
        value=current_text,
        height=300,
        key=f"prompt_text_{phase_key}_{selected_source}",
    )

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        # Save as new custom prompt
        new_name = st.text_input(
            "Neuer Prompt-Name",
            placeholder="z.B. 'Mein Style'",
            key=f"new_prompt_name_{phase_key}",
        )
        if st.button("Als neuen Prompt speichern", key=f"save_new_{phase_key}"):
            if not new_name or not new_name.strip():
                st.error("Bitte einen Namen eingeben.")
            elif new_name.strip() == "default":
                st.error("'default' ist reserviert.")
            else:
                name = new_name.strip()
                custom_prompts[name] = {
                    "phase": phase_key,
                    "text": edited_text,
                }
                active_prompts[phase_key] = name
                prefs["custom_prompts"] = custom_prompts
                prefs["active_prompts"] = active_prompts
                save_preferences(prefs)
                st.success(f"Prompt '{name}' gespeichert und aktiviert!")
                st.rerun()

    with col2:
        # Overwrite current custom prompt
        if not is_default:
            if st.button("Aenderungen speichern", key=f"overwrite_{phase_key}"):
                custom_prompts[selected_source]["text"] = edited_text
                prefs["custom_prompts"] = custom_prompts
                save_preferences(prefs)
                st.success(f"Prompt '{selected_source}' aktualisiert!")

    with col3:
        # Delete custom prompt (not default)
        if not is_default:
            if st.button("Prompt loeschen", key=f"delete_{phase_key}", type="secondary"):
                del custom_prompts[selected_source]
                if active_prompts.get(phase_key) == selected_source:
                    active_prompts.pop(phase_key, None)
                prefs["custom_prompts"] = custom_prompts
                prefs["active_prompts"] = active_prompts
                save_preferences(prefs)
                st.success(f"Prompt '{selected_source}' geloescht!")
                st.rerun()

    # Show default for comparison when viewing custom
    if not is_default:
        with st.expander("Default-Prompt anzeigen (zum Vergleich)"):
            st.code(get_default_prompt_text(phase_key), language=None)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def _render_preferences(prefs: dict):
    with st.form("prefs_form"):
        language = st.selectbox(
            "Standard-Sprache",
            LANGUAGES,
            index=LANGUAGES.index(prefs.get("default_language", "de")),
            format_func=lambda x: "Deutsch" if x == "de" else "English",
        )
        text_length = st.selectbox(
            "Standard-Textumfang",
            TEXT_LENGTHS,
            index=TEXT_LENGTHS.index(prefs.get("default_text_length", "medium")),
        )
        tonality = st.text_input("Tonalitaet", value=prefs.get("tonality", ""))
        custom_rules = st.text_area(
            "Eigene Regeln (eine pro Zeile)",
            value="\n".join(prefs.get("custom_rules", [])),
        )

        # Preferred templates — dynamic from active master
        available = get_available_template_types()
        labels = get_template_labels()
        current_preferred = [t for t in prefs.get("preferred_templates", []) if t in available]
        preferred_templates = st.multiselect(
            "Bevorzugte Templates (fuer Sektionsplanung)",
            options=available,
            default=current_preferred or available[:3],
            format_func=lambda t: labels.get(t, t),
        )

        if st.form_submit_button("Praeferenzen speichern"):
            prefs["default_language"] = language
            prefs["default_text_length"] = text_length
            prefs["tonality"] = tonality
            prefs["custom_rules"] = [r.strip() for r in custom_rules.split("\n") if r.strip()]
            prefs["preferred_templates"] = preferred_templates
            save_preferences(prefs)
            st.success("Praeferenzen gespeichert!")
