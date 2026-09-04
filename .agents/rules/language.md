# Rule: Language & Localization Policy

1. **Repository Artifacts (Strictly English):**
   - **Source Code:** All Python, Jinja2, SQL, Dockerfiles, and Makefile code.
   - **Identifiers:** Variable names, functions, classes, database tables/columns, route names, constants.
   - **Comments & Docstrings:** All in-code comments, method docstrings, and module descriptions.
   - **Technical Documentation:** `README.md`, all files in `docs/**/*.md`, architecture diagrams (Mermaid), and OpenAPI/Swagger descriptions (`help_text`, `@extend_schema`).
   - **Source i18n Strings (`msgid`):** The primary untranslated string in Python code must always be in English (e.g., `_("Invalid password.")`).
   - **Version Control:** Git commit messages, branch names, and changelogs.

2. **Explicit Exceptions (Non-English Allowed):**
   - **Translation Catalogs:** `locale/<lang>/LC_MESSAGES/django.po` and compiled `.mo` files (e.g., Spanish `msgstr`).
   - **Test Assertions for Translations:** String literals inside test cases asserting localized responses (e.g., `self.assertEqual(resp.data["detail"], "Contraseña actualizada exitosamente.")`).

3. **Assistant Interaction (Chat Interface):**
   - The assistant communicates with the user in the language used by the user (Spanish by default if prompted in Spanish).
   - Any proposed code diff, file creation, or documentation committed to the project must strictly follow points 1 and 2 regardless of the chat language.
