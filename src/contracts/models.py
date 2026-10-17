from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

NonBlankStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class NoticeTrigger(str, Enum):
    LOSS_DATE = "loss_date"
    DATE_OF_KNOWLEDGE = "date_of_knowledge"
    OTHER = "other"


class PlacementBasis(str, Enum):
    TREATY = "treaty"
    FACULTATIVE = "facultative"


class StructureType(str, Enum):
    QUOTA_SHARE = "quota_share"
    SURPLUS = "surplus"
    EXCESS_OF_LOSS = "excess_of_loss"
    STOP_LOSS = "stop_loss"
    CAT_XOL = "cat_xol"


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(ge=0, decimal_places=4)
    currency: Currency

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)


class Clause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: NonBlankStr
    title: str | None = None
    text: NonBlankStr
    source_document_id: NonBlankStr
    location: NonBlankStr


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: NonBlankStr
    title: NonBlankStr
    clauses: list[Clause] = Field(default_factory=list)


class Layer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: NonBlankStr
    section_id: NonBlankStr
    currency: Currency
    retention: Money | None = None
    limit: Money | None = None
    share_percent: Decimal = Field(gt=0, le=100)
    inception: date
    expiry: date

    @field_serializer("share_percent", when_used="json")
    def serialize_share_percent(self, value: Decimal) -> str:
        return str(value)

    @model_validator(mode="after")
    def validate_terms(self) -> Layer:
        if self.expiry <= self.inception:
            raise ValueError("expiry must be after inception")
        if (
            self.retention is not None
            and self.retention.currency != self.currency
        ):
            raise ValueError("retention currency must match Layer.currency")
        if self.limit is not None and self.limit.currency != self.currency:
            raise ValueError("limit currency must match Layer.currency")
        return self


class NoticeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: NoticeTrigger
    trigger_description: NonBlankStr | None = None
    period_days: int | None = Field(default=None, ge=0)
    clause_id: NonBlankStr

    @model_validator(mode="after")
    def validate_description(self) -> NoticeRule:
        if self.trigger is NoticeTrigger.OTHER and self.trigger_description is None:
            raise ValueError(
                "trigger_description is required when trigger is 'other'"
            )
        if self.period_days is None and self.trigger_description is None:
            raise ValueError(
                "trigger_description is required when period_days is null"
            )
        return self


class ContractVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_label: NonBlankStr
    effective_from: date
    effective_to: date | None = None
    sections: list[Section] = Field(default_factory=list)
    layers: list[Layer] = Field(min_length=1)
    notice_rules: list[NoticeRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_version(self) -> ContractVersion:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")

        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section_id values must be unique within a version")

        clauses = [
            clause for section in self.sections for clause in section.clauses
        ]
        clause_ids = [clause.clause_id for clause in clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("clause_id values must be unique across all sections")

        layer_ids = [layer.layer_id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("layer_id values must be unique within a version")

        known_section_ids = set(section_ids)
        for layer in self.layers:
            if layer.section_id not in known_section_ids:
                raise ValueError(
                    f"layer {layer.layer_id} section_id references no section"
                )

        known_clause_ids = set(clause_ids)
        for rule in self.notice_rules:
            if rule.clause_id not in known_clause_ids:
                raise ValueError("notice rule clause_id references no clause")

        for layer in self.layers:
            if layer.inception < self.effective_from:
                raise ValueError(
                    f"layer {layer.layer_id} inception must be on or after "
                    "effective_from"
                )
            if self.effective_to is not None and layer.expiry >= self.effective_to:
                raise ValueError(
                    f"layer {layer.layer_id} expiry must be before effective_to"
                )

        return self


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: NonBlankStr
    placement_basis: PlacementBasis
    structure_type: StructureType
    cedent_name: NonBlankStr
    versions: list[ContractVersion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_versions(self) -> Contract:
        version_labels = [version.version_label for version in self.versions]
        if len(version_labels) != len(set(version_labels)):
            raise ValueError("version_label values must be unique within a contract")

        for index, version in enumerate(self.versions):
            for other in self.versions[index + 1 :]:
                overlaps = (
                    version.effective_to is None
                    or other.effective_from < version.effective_to
                ) and (
                    other.effective_to is None
                    or version.effective_from < other.effective_to
                )
                if overlaps:
                    raise ValueError(
                        f"effective ranges for versions {version.version_label} "
                        f"and {other.version_label} must not overlap"
                    )

        return self
