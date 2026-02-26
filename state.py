class ResumeState:
    def __init__(self):
        self.data = {
            "name": None,
            "email": None,
            "phone": None,
            "linkedin": None,
            "github": None,
            "summary": None,
            "education": [],       # list of {institution, degree, year}
            "skills": [],
            "experience": [],      # list of {company, role, duration, bullets[]}
            "projects": [],        # list of {name, description, tech_stack[]}
        }

    def update(self, new_data: dict):
        for field, value in new_data.items():
            if not value:
                continue

            if field not in self.data:
                continue

            # Handle list-based fields
            if isinstance(self.data.get(field), list):
                if isinstance(value, list):
                    for item in value:
                        if item not in self.data[field]:
                            self.data[field].append(item)

            # Handle single-value fields (set once, update if explicitly provided)
            else:
                self.data[field] = value

    def set_field(self, field: str, value):
        """Directly set a field to a given value (for manual edits)."""
        if field in self.data:
            self.data[field] = value

    def delete_from_field(self, field: str, details: str = None, index: int = None):
        """Delete a value or item from a resume field.

        - For simple string fields: resets to None
        - For list fields: removes by index or by matching details string
        """
        if field not in self.data:
            return False

        current = self.data[field]

        # Simple field -- reset to None
        if not isinstance(current, list):
            self.data[field] = None
            return True

        # List field -- remove by index
        if index is not None and 0 <= index < len(current):
            self.data[field].pop(index)
            return True

        # List of strings (skills) -- remove by value match
        if details and current and isinstance(current[0], str):
            lower_details = details.lower()
            self.data[field] = [
                item for item in current
                if lower_details not in item.lower()
            ]
            return True

        # List of dicts (experience, education, projects) -- match by details
        if details and current and isinstance(current[0], dict):
            lower_details = details.lower()
            self.data[field] = [
                item for item in current
                if lower_details not in str(item).lower()
            ]
            return True

        return False

    def replace_all(self, new_data: dict):
        """Replace the entire resume data (used after professionalization)."""
        for field, value in new_data.items():
            if field in self.data:
                self.data[field] = value

    def get_resume_data(self):
        """Return a copy of the resume data dict for template rendering."""
        return dict(self.data)

    def missing_fields(self):
        missing = []
        for field, value in self.data.items():
            if value is None or value == []:
                missing.append(field)
        return missing

    def is_empty(self):
        """Check if resume has no data at all."""
        for value in self.data.values():
            if value is not None and value != []:
                return False
        return True