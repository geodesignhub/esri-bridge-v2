from data_definitions import AGOLItemSchema, ESRIFieldDefinition


class AGOLItemSchemaGenerator:
    def __init__(self, item_name) -> None:
        self.field_definitions = [
            ESRIFieldDefinition(
                name="project_or_policy",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Project or policy",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="diagram_name",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Diagram name",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="color",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Color",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="diagram_id",
                type_="esriFieldTypeInteger",
                sqlType="sqlTypeInteger",
                alias="Diagram id",
                precision=0,
            ),
            ESRIFieldDefinition(
                name="tag_codes",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Tag codes",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="start_date",
                type_="esriFieldTypeDate",
                sqlType="sqlTypeDate",
                alias="Start date",
                precision=1,
            ),
            ESRIFieldDefinition(
                name="end_date",
                type_="esriFieldTypeDate",
                sqlType="sqlTypeDate",
                alias="End date",
                precision=1,
            ),
            ESRIFieldDefinition(
                name="notes",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Notes",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="grid_location",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="Grid location",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="system_name",
                type_="esriFieldTypeString",
                sqlType="sqlTypeNVarchar",
                alias="System name",
                length=255,
                precision=0,
            ),
            ESRIFieldDefinition(
                name="ObjectID",
                type_="esriFieldTypeOID",
                sqlType="sqlTypeOther",
                alias="Objectid",
                precision=0,
            ),
            ESRIFieldDefinition(
                name="Shape__Area",
                type_="esriFieldTypeDouble",
                sqlType="sqlTypeDouble",
                alias="Shape  area",
                precision=0,
            ),
            ESRIFieldDefinition(
                name="Shape__Length",
                type_="esriFieldTypeDouble",
                sqlType="sqlTypeDouble",
                alias="Shape  length",
                precision=0,
            ),
        ]
        self.esri_field_schema = AGOLItemSchema(
            field_definitions=self.field_definitions, item_name=item_name
        )

        self.publish_parameters = self.esri_field_schema.publish_parameters
