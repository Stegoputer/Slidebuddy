import streamlit as st

from slidebuddy.config.defaults import (
    LANGUAGES,
    TEXT_LENGTHS,
    get_all_api_keys,
    get_available_template_types,
    get_template_labels,
    load_preferences,
    save_preferences,
    set_api_key,
)
from slidebuddy.llm.prompt_assembler import PROMPT_PHASES, get_default_prompt_text
from slidebuddy.llm.router import clear_llm_cache, clear_models_cache, get_provider_models


def render_settings():
    st.header("⚙️ Einstellungen")

    prefs = load_preferences()

    tabs = st.tabs([
        "API-Keys",
        "Modelle",
        "Generierung",
        "RAG & Retrieval",
        "Prompts",
        "Praeferenzen",
    ])

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
    st.subheader("API-Keys")
    st.caption("Keys werden sicher im Windows Credential Manager gespeichert.")

    api_keys = get_all_api_keys()

    # Status overview
    providers = [
        ("Anthropic", "anthropic", "Claude-Modelle"),
        ("OpenAI", "openai", "GPT + Embeddings"),
        ("Google AI", "google", "Gemini-Modelle"),
    ]
    cols = st.columns(len(providers))
    for col, (name, key, desc) in zip(cols, providers):
        with col:
            has_key = bool(api_keys.get(key, ""))
            st.metric(name, "Aktiv" if has_key else "Fehlt")
            st.caption(desc)

    st.markdown("")

    with st.form("api_keys_form"):
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=api_keys.get("anthropic", ""),
            type="password",
        )
        openai_key = st.text_input(
            "OpenAI API Key",
            value=api_keys.get("openai", ""),
            type="password",
        )
        google_key = st.text_input(
            "Google AI API Key",
            value=api_keys.get("google", ""),
            type="password",
        )

        st.markdown("")
        if st.form_submit_button("Speichern", use_container_width=True):
            set_api_key("anthropic", anthropic_key)
            set_api_key("openai", openai_key)
            set_api_key("google", google_key)
            clear_llm_cache()
            clear_models_cache()
            st.success("API-Keys sicher im OS Keyring gespeichert!")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def _render_models(prefs: dict):
    st.subheader("Modellauswahl")
    st.caption("Waehle fuer jede Phase das passende LLM.")

    provider_models = get_provider_models()
    all_models = []
    for models in provider_models.values():
        all_models.extend(models)

    if not all_models:
        st.warning("Keine Modelle verfuegbar. Bitte zuerst API-Keys eintragen.")
        return

    default_models = prefs.get("default_models", {})

    # Current model overview
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Planung", default_models.get("planning", all_models[0]).split("/")[-1] if default_models.get("planning") else "—")
    with col2:
        st.metric("Generierung", default_models.get("generation", all_models[0]).split("/")[-1] if default_models.get("generation") else "—")
    with col3:
        st.metric("Master-Analyse", default_models.get("master_analysis", all_models[0]).split("/")[-1] if default_models.get("master_analysis") else "—")
    with col4:
        st.metric("Embeddings", default_models.get("embedding", "text-embedding-3-small"))

    st.markdown("")

    with st.form("models_form"):
        planning_model = st.selectbox(
            "Kapitel- & Sektionsplanung",
            all_models,
            index=all_models.index(default_models.get("planning", all_models[0])) if default_models.get("planning") in all_models else 0,
            help="Schnellere Modelle reichen fuer Planung.",
        )

        generation_model = st.selectbox(
            "Slide-Generierung",
            all_models,
            index=all_models.index(default_models.get("generation", all_models[0])) if default_models.get("generation") in all_models else 0,
            help="Staerkere Modelle liefern bessere Inhalte.",
        )

        master_analysis_model = st.selectbox(
            "Master-Analyse (Layout-Erkennung)",
            all_models,
            index=all_models.index(default_models.get("master_analysis", all_models[0])) if default_models.get("master_analysis") in all_models else 0,
            help="Analysiert PPTX-Layouts und generiert Purpose/Beschreibung. Staerkere Modelle (z.B. Claude Opus) liefern bessere Ergebnisse.",
        )

        embedding_model = st.selectbox(
            "Embedding-Modell",
            ["text-embedding-3-small", "text-embedding-3-large"],
            index=0,
            help="'small' ist schneller und guenstiger.",
        )

        st.markdown("")
        if st.form_submit_button("Speichern", use_container_width=True):
            prefs["default_models"] = {
                "planning": planning_model,
                "generation": generation_model,
                "master_analysis": master_analysis_model,
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
    st.caption("Steuert wie viele Folien pro LLM-Aufruf generiert werden.")

    current_batch = prefs.get("batch_size", 4)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Batch-Groesse", f"{current_batch} Folien")
    with col2:
        st.metric("Empfehlung", "3–5 Folien")

    batch_size = st.slider(
        "Folien pro Batch",
        min_value=1,
        max_value=8,
        value=current_batch,
        key="settings_batch_size",
        help="Mehr Folien pro Batch = schneller, aber weniger Kontrolle.",
    )

    if st.button("Speichern", key="save_strategy", use_container_width=True):
        prefs["batch_size"] = batch_size
        save_preferences(prefs)
        st.success("Batch-Groesse gespeichert!")

    st.divider()

    # Debug section
    st.subheader("Prompt-Debug-Modus")
    st.caption("Loggt jeden LLM-Aufruf mit vollstaendigem Prompt, Chunks und Antwort.")

    debug_on = st.toggle(
        "Debug-Logging aktivieren",
        value=prefs.get("debug_prompts", False),
        help="Schreibt in data/prompt_debug.jsonl",
    )
    if debug_on != prefs.get("debug_prompts", False):
        prefs["debug_prompts"] = debug_on
        save_preferences(prefs)
        st.success("Debug-Modus " + ("aktiviert" if debug_on else "deaktiviert"))

    if debug_on:
        from slidebuddy.llm.prompt_logger import get_log_summary, clear_log, LOG_PATH
        summary = get_log_summary()
        if summary["total_calls"] > 0:
            # Stats in metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Calls", summary["total_calls"])
            m2.metric("Input-Tokens", f"~{summary['total_input_tokens']:,}")
            m3.metric("Output-Tokens", f"~{summary['total_output_tokens']:,}")
            m4.metric("Dauer", f"{summary['total_duration_s']}s")

            # Per-phase breakdown
            with st.expander("Details pro Phase"):
                for phase, stats in summary.get("by_phase", {}).items():
                    st.caption(
                        f"**{phase}**: {stats['calls']}x | "
                        f"~{stats['input_tokens']:,} in | "
                        f"~{stats['output_tokens']:,} out | "
                        f"{round(stats['duration_s'], 1)}s"
                    )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Log loeschen", key="clear_debug_log", use_container_width=True):
                    clear_log()
                    st.rerun()
            with col2:
                if LOG_PATH.exists():
                    st.download_button(
                        "📥 Log herunterladen",
                        LOG_PATH.read_bytes(),
                        file_name="prompt_debug.jsonl",
                        mime="application/jsonl",
                        key="download_debug_log",
                        use_container_width=True,
                    )
        else:
            st.info("Noch keine Calls geloggt. Starte eine Generierung.")


# ---------------------------------------------------------------------------
# RAG Settings
# ---------------------------------------------------------------------------

def _render_rag_settings(prefs: dict):
    rag = prefs.get("rag", {})

    # Overview metrics
    st.subheader("RAG & Retrieval")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chunks Planung", rag.get("n_sources_planning", 5))
    m2.metric("Chunks Generierung", rag.get("n_sources_generation", 3))
    m3.metric("Chunk-Groesse", f"{rag.get('chunk_size', 500)} Tok")
    m4.metric("Kontext-Limit", f"{rag.get('max_context_chars', 6000):,} Z")

    st.markdown("")

    with st.form("rag_form"):
        # --- Retrieval ---
        st.markdown("**Retrieval (Quellensuche)**")
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Planung")
            n_sources_planning = st.slider(
                "Quell-Chunks",
                min_value=1, max_value=20,
                value=rag.get("n_sources_planning", 5),
                help="Chunks fuer die Sektionsplanung",
                key="rag_src_plan",
            )
            n_global_planning = st.slider(
                "Globale Slides",
                min_value=0, max_value=10,
                value=rag.get("n_global_planning", 3),
                help="Wiederverwendbare Slides aus frueheren Projekten",
                key="rag_glob_plan",
            )
        with col2:
            st.caption("Generierung")
            n_sources_generation = st.slider(
                "Quell-Chunks",
                min_value=1, max_value=20,
                value=rag.get("n_sources_generation", 3),
                help="Chunks fuer die Slide-Erstellung",
                key="rag_src_gen",
            )
            n_global_generation = st.slider(
                "Globale Slides",
                min_value=0, max_value=10,
                value=rag.get("n_global_generation", 2),
                help="Wiederverwendbare Slides bei der Generierung",
                key="rag_glob_gen",
            )

        st.divider()

        # --- Auto-Chunk + Context ---
        st.markdown("**Chunk-Zuordnung & Kontext**")
        col3, col4 = st.columns(2)
        with col3:
            n_chunks_per_slide = st.slider(
                "Chunks pro Folie",
                min_value=1, max_value=10,
                value=rag.get("n_chunks_per_slide", 3),
                help="Mehr Chunks = mehr Kontext, aber auch mehr Tokens",
            )
        with col4:
            max_context_chars = st.slider(
                "Max. Zeichen im Prompt",
                min_value=1000, max_value=30000, step=500,
                value=rag.get("max_context_chars", 6000),
                help="Groessere Werte = mehr Kontext, mehr Tokens.",
            )

        st.divider()

        # --- Chunking ---
        st.markdown("**Chunking (Textaufteilung)**")
        st.caption("Aenderungen wirken nur bei neuem Upload.")
        col5, col6 = st.columns(2)
        with col5:
            chunk_size = st.slider(
                "Chunk-Groesse (Tokens)",
                min_value=100, max_value=2000, step=50,
                value=rag.get("chunk_size", 500),
                help="~4 Zeichen pro Token.",
            )
        with col6:
            chunk_overlap = st.slider(
                "Ueberlappung (Tokens)",
                min_value=0, max_value=500, step=10,
                value=rag.get("chunk_overlap", 50),
                help="Verhindert Informationsverlust an Chunk-Grenzen.",
            )

        st.markdown("")
        if st.form_submit_button("Speichern", use_container_width=True):
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

    # Migration button outside form
    st.divider()
    st.subheader("Distanzmetrik migrieren")
    st.caption(
        "Stellt bestehende ChromaDB-Collections von L2 auf Cosine-Distanz um. "
        "Danach zeigen Relevanzwerte sinnvolle Prozentwerte (0-100%)."
    )
    if st.button("Collections auf Cosine migrieren", key="migrate_cosine", use_container_width=True):
        from slidebuddy.rag.chroma_manager import migrate_to_cosine
        with st.spinner("Migriere Collections..."):
            count = migrate_to_cosine()
        if count > 0:
            st.success(f"{count} Collection(s) auf Cosine migriert.")
        else:
            st.info("Alle Collections nutzen bereits Cosine.")


# ---------------------------------------------------------------------------
# Prompt Editor
# ---------------------------------------------------------------------------

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
    st.caption(
        "Bearbeite die System-Prompts fuer jede Phase. "
        "Du kannst eigene Varianten erstellen und zwischen ihnen wechseln."
    )

    custom_prompts = prefs.get("custom_prompts", {})
    active_prompts = prefs.get("active_prompts", {})

    # Phase selection in two columns
    col1, col2 = st.columns(2)
    with col1:
        group = st.selectbox(
            "Kategorie",
            list(_EDITABLE_PHASES.keys()),
            key="prompt_group",
        )
    with col2:
        phases = _EDITABLE_PHASES[group]
        phase_key = st.selectbox(
            "Prompt",
            phases,
            format_func=lambda k: _PHASE_LABELS.get(k, k),
            key="prompt_phase",
        )

    # Active prompt source
    matching_custom = {
        name: p for name, p in custom_prompts.items()
        if p.get("phase") == phase_key
    }

    source_options = ["default"] + list(matching_custom.keys())
    active_source = active_prompts.get(phase_key, "default")
    if active_source not in source_options:
        active_source = "default"

    selected_source = st.selectbox(
        "Aktiver Prompt",
        source_options,
        index=source_options.index(active_source),
        format_func=lambda s: "🔒 Default (nicht loeschbar)" if s == "default" else f"📝 {s}",
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
        height=350,
        key=f"prompt_text_{phase_key}_{selected_source}",
    )

    # Action buttons
    st.markdown("")  # spacing
    col1, col2, col3 = st.columns(3)

    with col1:
        new_name = st.text_input(
            "Name fuer neuen Prompt",
            placeholder="z.B. 'Mein Style'",
            key=f"new_prompt_name_{phase_key}",
        )
        if st.button("➕ Als neuen Prompt speichern", key=f"save_new_{phase_key}", use_container_width=True):
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
        if not is_default:
            st.markdown("")  # align with text_input above
            st.markdown("")
            if st.button("💾 Aenderungen speichern", key=f"overwrite_{phase_key}", use_container_width=True):
                custom_prompts[selected_source]["text"] = edited_text
                prefs["custom_prompts"] = custom_prompts
                save_preferences(prefs)
                st.success(f"Prompt '{selected_source}' aktualisiert!")

    with col3:
        if not is_default:
            st.markdown("")
            st.markdown("")
            if st.button("🗑️ Prompt loeschen", key=f"delete_{phase_key}", use_container_width=True, type="secondary"):
                del custom_prompts[selected_source]
                if active_prompts.get(phase_key) == selected_source:
                    active_prompts.pop(phase_key, None)
                prefs["custom_prompts"] = custom_prompts
                prefs["active_prompts"] = active_prompts
                save_preferences(prefs)
                st.success(f"Prompt '{selected_source}' geloescht!")
                st.rerun()

    # Show default for comparison
    if not is_default:
        with st.expander("🔍 Default-Prompt anzeigen (zum Vergleich)"):
            st.code(get_default_prompt_text(phase_key), language=None)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def _render_preferences(prefs: dict):
    st.subheader("Praeferenzen")
    st.caption("Globale Standardwerte fuer neue Projekte.")

    _length_labels = {"short": "Kurz", "medium": "Mittel", "long": "Ausfuehrlich"}
    _lang_labels = {"de": "Deutsch", "en": "English"}

    # Overview
    col1, col2, col3 = st.columns(3)
    col1.metric("Sprache", _lang_labels.get(prefs.get("default_language", "de"), "—"))
    col2.metric("Textumfang", _length_labels.get(prefs.get("default_text_length", "medium"), "—"))
    col3.metric("Tonalitaet", prefs.get("tonality", "—") or "—")

    st.markdown("")

    with st.form("prefs_form"):
        col1, col2 = st.columns(2)

        with col1:
            language = st.selectbox(
                "Standard-Sprache",
                LANGUAGES,
                index=LANGUAGES.index(prefs.get("default_language", "de")),
                format_func=lambda x: _lang_labels.get(x, x),
            )
            text_length = st.selectbox(
                "Standard-Textumfang",
                TEXT_LENGTHS,
                index=TEXT_LENGTHS.index(prefs.get("default_text_length", "medium")),
                format_func=lambda x: _length_labels.get(x, x),
            )

        with col2:
            tonality = st.text_input(
                "Tonalitaet",
                value=prefs.get("tonality", ""),
                placeholder="z.B. 'professionell', 'locker', 'wissenschaftlich'",
            )

        st.divider()

        custom_rules = st.text_area(
            "Eigene Regeln (eine pro Zeile)",
            value="\n".join(prefs.get("custom_rules", [])),
            height=100,
            placeholder="z.B. 'Keine Anglizismen verwenden'\n'Immer Quellenangaben nennen'",
        )

        # Preferred templates
        available = get_available_template_types()
        labels = get_template_labels()
        current_preferred = [t for t in prefs.get("preferred_templates", []) if t in available]
        preferred_templates = st.multiselect(
            "Bevorzugte Templates (fuer Sektionsplanung)",
            options=available,
            default=current_preferred or available[:3],
            format_func=lambda t: labels.get(t, t),
        )

        st.markdown("")
        if st.form_submit_button("Speichern", use_container_width=True):
            prefs["default_language"] = language
            prefs["default_text_length"] = text_length
            prefs["tonality"] = tonality
            prefs["custom_rules"] = [r.strip() for r in custom_rules.split("\n") if r.strip()]
            prefs["preferred_templates"] = preferred_templates
            save_preferences(prefs)
            st.success("Praeferenzen gespeichert!")
