import config

def load_project_skills():
    skill_blocks = []

    if not config.SKILLS_ROOT.exists():
        return skill_blocks

    for skill_dir in config.SKILLS_ROOT.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        reference_md = skill_dir / "reference.md"
        scripts_dir = skill_dir / "scripts"

        parts = []

        if skill_md.exists():
            parts.append("# SKILL.md\n" + skill_md.read_text(encoding="utf-8"))

        if reference_md.exists():
            parts.append("# reference.md\n" + reference_md.read_text(encoding="utf-8"))

        if scripts_dir.exists():
            script_files = sorted(
                p for p in scripts_dir.iterdir()
                if p.is_file() and p.suffix in [".py", ".sh"]
            )

            if script_files:
                scripts_list = "\n".join(
                    f"- {p.name}: {p}"
                    for p in script_files
                )

                parts.append(
                    "# scripts/\n"
                    "These scripts are available on the local device. "
                    "The assistant cannot execute them directly from memory. "
                    "When needed, the Python app must call them as client-side tools.\n\n"
                    f"{scripts_list}"
                )

        if not parts:
            continue

        skill_blocks.append(
            {
                "label": f"skill_{skill_name.replace('-', '_')}",
                "value": "\n\n".join(parts)[:6000],
            }
        )

    return skill_blocks