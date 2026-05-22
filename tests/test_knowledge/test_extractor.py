"""Unit tests — entity extraction via regex patterns."""

from rag_ocpp.knowledge.entities import OCPPEntityType, extract_entity_names


class TestExtraction:
    def test_commands(self):
        n = extract_entity_names("Authorize.req and BootNotification.conf", OCPPEntityType.COMMAND)
        assert "Authorize" in n and "BootNotification" in n

    def test_datatypes(self):
        n = extract_entity_names("IdToken in ChargingProfile", OCPPEntityType.DATATYPE)
        assert "IdToken" in n and "ChargingProfile" in n

    def test_components(self):
        n = extract_entity_names("ChargePoint to CSMS via Connector", OCPPEntityType.COMPONENT)
        assert "ChargePoint" in n and "CSMS" in n and "Connector" in n

    def test_enums(self):
        n = extract_entity_names("ChargingState enum", OCPPEntityType.ENUM)
        assert "ChargingState" in n

    def test_errors(self):
        n = extract_entity_names("NotSupported or InternalError", OCPPEntityType.ERROR_CODE)
        assert "NotSupported" in n and "InternalError" in n

    def test_test_cases(self):
        n = extract_entity_names("TC_OC_01 and TC_CS_42", OCPPEntityType.TEST_CASE)
        assert "TC_OC_01" in n and "TC_CS_42" in n

    def test_all_types(self):
        text = "Authorize.req uses IdToken. Core block. ChargePoint → CSMS. NotSupported. ChargingState. TC_AU_05."
        n = extract_entity_names(text)
        assert len(n) >= 6

    def test_no_false_positives(self):
        n = extract_entity_names("cats and dogs are nice animals")
        assert "cats" not in n and "dogs" not in n
