from data_definitions import AGOLItemSchema, ESRIFieldDefinition


class AGOLItemSchemaGenerator:
    def __init__(self, item_name) -> None:
        self.field_definitions = [
            ESRIFieldDefinition(
                name="project_or_policy",
                type="esriFieldTypeString",
                sql_type="sqlTypeNVarchar",
            ),
            ESRIFieldDefinition(
                name="diagram_name",
                type="esriFieldTypeString",
                sql_type="sqlTypeNVarchar",
            ),
            ESRIFieldDefinition(
                name="color", type="esriFieldTypeString", sql_type="sqlTypeNVarchar"
            ),
            ESRIFieldDefinition(
                name="diagram_id",
                type="esriFieldTypeInteger",
                sql_type="sqlTypeInteger",
            ),
            ESRIFieldDefinition(
                name="tag_codes", type="esriFieldTypeString", sql_type="sqlTypeNVarchar"
            ),
            ESRIFieldDefinition(
                name="start_date", type="esriFieldTypeDate", sql_type="sqlTypeDate"
            ),
            ESRIFieldDefinition(
                name="end_date", type="esriFieldTypeDate", sql_type="sqlTypeDate"
            ),
            ESRIFieldDefinition(
                name="notes", type="esriFieldTypeString", sql_type="sqlTypeNVarchar"
            ),
            ESRIFieldDefinition(
                name="grid_location",
                type="esriFieldTypeString",
                sql_type="sqlTypeNVarchar",
            ),
            ESRIFieldDefinition(
                name="system_name",
                type="esriFieldTypeString",
                sql_type="sqlTypeNVarchar",
            ),
            ESRIFieldDefinition(
                name="ObjectID", type="esriFieldTypeOID", sql_type="sqlTypeOther"
            ),
            ESRIFieldDefinition(
                name="Shape__Area", type="esriFieldTypeDouble", sql_type="sqlTypeDouble"
            ),
            ESRIFieldDefinition(
                name="Shape__Length",
                type="esriFieldTypeDouble",
                sql_type="sqlTypeDouble",
            ),
        ]
        self.esri_field_schema = AGOLItemSchema(
            field_definitions=self.field_definitions, item_name=item_name
        )
        self.publish_parameters = self.esri_field_schema.publish_parameters
