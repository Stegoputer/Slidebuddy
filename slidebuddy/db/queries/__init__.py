"""DB query functions — one module per entity, re-exported here for backward compat.

Import from this package directly:
    from slidebuddy.db.queries import create_slide, get_project
"""

from .project import (
    create_project,
    get_project,
    get_all_projects,
    update_project,
    delete_project,
)
from .source import (
    create_source,
    get_sources_for_project,
    update_source_status,
    delete_source,
)
from .chapter import (
    create_chapter,
    get_chapters_for_project,
    update_chapter_status,
)
from .slide import (
    create_slide,
    get_slides_for_chapter,
    get_slides_for_project,
    update_slide,
)
from .version import (
    create_version,
    get_versions_for_project,
)
from .source_gap import (
    create_source_gap,
    get_source_gaps_for_project,
    update_source_gap_status,
)
from .section_plan import (
    save_section_plan,
    get_section_plan,
    get_all_section_plans,
    delete_section_plans_for_project,
)
from .master import (
    create_slide_master,
    get_all_slide_masters,
    get_slide_master,
    get_active_slide_master,
    set_active_slide_master,
    delete_slide_master,
    create_master_template,
    get_templates_for_master,
    get_active_master_templates,
    update_master_template,
    get_available_template_types,
    get_template_labels,
)

__all__ = [
    # project
    "create_project", "get_project", "get_all_projects", "update_project", "delete_project",
    # source
    "create_source", "get_sources_for_project", "update_source_status", "delete_source",
    # chapter
    "create_chapter", "get_chapters_for_project", "update_chapter_status",
    # slide
    "create_slide", "get_slides_for_chapter", "get_slides_for_project", "update_slide",
    # version
    "create_version", "get_versions_for_project",
    # source_gap
    "create_source_gap", "get_source_gaps_for_project", "update_source_gap_status",
    # master
    "create_slide_master", "get_all_slide_masters", "get_slide_master",
    "get_active_slide_master", "set_active_slide_master", "delete_slide_master",
    "create_master_template", "get_templates_for_master", "get_active_master_templates",
    "update_master_template", "get_available_template_types", "get_template_labels",
    # section_plan
    "save_section_plan", "get_section_plan", "get_all_section_plans",
    "delete_section_plans_for_project",
]
