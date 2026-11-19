"""Чтение сохранённых значений из XLSX."""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_xlsx(data: bytes) -> dict:
    """Прочитать значения OOXML; формулы допускаются только с сохранённым значением."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(n.text or "" for n in x.findall(".//s:t", NS)) for x in root.findall("s:si", NS)]
        rels = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        result = {}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rel].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            rows = []
            for row in ET.fromstring(archive.read(target)).findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    value = cell.findtext("s:v", "", NS)
                    kind = cell.attrib.get("t")
                    if kind == "s" and value != "":
                        value = shared[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(n.text or "" for n in cell.findall(".//s:t", NS))
                    elif value != "" and kind not in ("str", "e", "b"):
                        number = float(value)
                        value = int(number) if number.is_integer() else number
                    if value != "":
                        cells[re.sub(r"\d", "", cell.attrib["r"])] = value
                if cells:
                    rows.append({"row": int(row.attrib["r"]), "cells": cells})
            result[sheet.attrib["name"]] = rows
        return result
