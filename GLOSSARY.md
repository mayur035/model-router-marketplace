# Model routing

Sending each piece of coding work to a fast, standard or deep model, by the project's own rules or a built-in rubric.

## Language

**Rules file**:
The per-project file that says which tier handles which kind of work, and whether routing happens automatically.
_Avoid_: config, settings, routing config

**Project root**:
The folder a rules file belongs to: the Claude Code project folder when known, otherwise the folder the session is working in.
_Avoid_: cwd, workspace

**Legacy rules file**:
The rules file in its old location. It is still read, never created, and loses to the current location when both exist.
_Avoid_: old config

**Auto-routing**:
Reminding the main agent on every prompt to route coding work, without the user asking.
_Avoid_: auto mode
