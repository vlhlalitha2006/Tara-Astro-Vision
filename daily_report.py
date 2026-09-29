import base64
import datetime
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

try:
    from main import ADMIN_EMAIL, DATABASE_URL, send_email
except ImportError:
    print("Could not import main.py configuration.")
    sys.exit(1)


SUCCESS_STATUSES = {"confirmed", "paid", "success", "successful"}
FAILED_STATUSES = {"failed", "cancelled", "canceled", "declined"}
EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NOT_RECORDED = "Not recorded"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", REL_NS)


def _booking_record(booking):
    keys = booking.keys()
    participants = []
    try:
        participants = json.loads(booking["participants"] or "[]")
    except (KeyError, TypeError, json.JSONDecodeError):
        pass

    customer_name = booking["customer_name"] if "customer_name" in keys else None
    if not customer_name and participants and isinstance(participants[0], dict):
        customer_name = participants[0].get("name")

    status = str(booking["status"] or "pending").strip()
    normalized_status = status.casefold().replace("_", " ")
    if normalized_status in SUCCESS_STATUSES:
        payment_status = "Successful"
        status_group = "successful"
    elif normalized_status in FAILED_STATUSES:
        payment_status = "Cancelled" if normalized_status in {"cancelled", "canceled"} else "Failed"
        status_group = "failed"
    else:
        payment_status = normalized_status.title()
        status_group = "pending"

    amount = float(booking["price"] or 0)
    quantity = max(1, int(booking["persons"] or 1))
    item_name = str(booking["name"] or "Service")
    item_type = str(booking["type"] or "Service").title()
    item_price = amount / quantity
    item_line = (
        f"{item_type}: {item_name} — Quantity/persons: {quantity} — "
        f"Item price: ₹{item_price:,.2f} — Line total: ₹{amount:,.2f}"
    )

    return {
        "customer_name": str(customer_name or NOT_RECORDED),
        "customer_email": str(booking["contact_email"] or NOT_RECORDED),
        "customer_phone": str(booking["contact_phone"] or NOT_RECORDED),
        "booking_id": str(booking["id"]),
        "booking_datetime": str(booking["created_at"] or NOT_RECORDED),
        "item_line": item_line,
        "quantity": quantity,
        "item_price": item_price,
        "total_amount": amount,
        "payment_status": payment_status,
        "status_group": status_group,
        "razorpay_order_id": str(booking["razorpay_order_id"] or NOT_RECORDED)
        if "razorpay_order_id" in keys else NOT_RECORDED,
        "razorpay_payment_id": str(booking["razorpay_payment_id"] or NOT_RECORDED)
        if "razorpay_payment_id" in keys else NOT_RECORDED,
    }


def _excel_safe(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _worksheet_xml(rows, widths, last_column):
    tag = lambda name: f"{{{MAIN_NS}}}{name}"
    worksheet = ET.Element(tag("worksheet"))
    views = ET.SubElement(worksheet, tag("sheetViews"))
    view = ET.SubElement(views, tag("sheetView"), {"workbookViewId": "0"})
    ET.SubElement(view, tag("pane"), {
        "ySplit": "1", "topLeftCell": "A2", "activePane": "bottomLeft", "state": "frozen"
    })
    columns = ET.SubElement(worksheet, tag("cols"))
    for index, width in enumerate(widths, 1):
        ET.SubElement(columns, tag("col"), {
            "min": str(index), "max": str(index), "width": str(width), "customWidth": "1"
        })

    sheet_data = ET.SubElement(worksheet, tag("sheetData"))
    for row_index, values in enumerate(rows, 1):
        row = ET.SubElement(sheet_data, tag("row"), {"r": str(row_index)})
        for column_index, value in enumerate(values, 1):
            reference = f"{_column_name(column_index)}{row_index}"
            cell = ET.SubElement(row, tag("c"), {"r": reference})
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                ET.SubElement(cell, tag("v")).text = str(value)
            else:
                cell.set("t", "inlineStr")
                inline = ET.SubElement(cell, tag("is"))
                ET.SubElement(inline, tag("t")).text = str(value)

    ET.SubElement(worksheet, tag("autoFilter"), {
        "ref": f"A1:{last_column}{len(rows)}"
    })
    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _create_workbook(records, summary):
    booking_rows = [[
        "Customer Name", "Customer Email", "Customer Phone", "Booking ID",
        "Booking Date and Time", "Booked Item/Service", "Quantity/Persons",
        "Individual Item Price", "Total Booking Amount", "Payment Status",
        "Razorpay Order ID", "Razorpay Payment ID",
    ]]
    for record in records:
        booking_rows.append([
            _excel_safe(record["customer_name"]),
            _excel_safe(record["customer_email"]),
            _excel_safe(record["customer_phone"]),
            _excel_safe(record["booking_id"]),
            _excel_safe(record["booking_datetime"]),
            _excel_safe(record["item_line"]),
            record["quantity"],
            record["item_price"],
            record["total_amount"],
            _excel_safe(record["payment_status"]),
            _excel_safe(record["razorpay_order_id"]),
            _excel_safe(record["razorpay_payment_id"]),
        ])

    summary_rows = [["Metric", "Value"], *summary.items()]
    workbook = ET.Element(f"{{{MAIN_NS}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    for index, name in enumerate(("Daily Bookings", "Daily Summary"), 1):
        ET.SubElement(sheets, f"{{{MAIN_NS}}}sheet", {
            "name": name,
            "sheetId": str(index),
            f"{{{REL_NS}}}id": f"rId{index}",
        })

    package_relationships = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(package_relationships, f"{{{PKG_REL_NS}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        "Target": "xl/workbook.xml",
    })
    workbook_relationships = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    for index in (1, 2):
        ET.SubElement(workbook_relationships, f"{{{PKG_REL_NS}}}Relationship", {
            "Id": f"rId{index}",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": f"worksheets/sheet{index}.xml",
        })

    content_types = ET.Element(f"{{{CONTENT_NS}}}Types")
    ET.SubElement(content_types, f"{{{CONTENT_NS}}}Default", {
        "Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"
    })
    ET.SubElement(content_types, f"{{{CONTENT_NS}}}Default", {
        "Extension": "xml", "ContentType": "application/xml"
    })
    ET.SubElement(content_types, f"{{{CONTENT_NS}}}Override", {
        "PartName": "/xl/workbook.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    })
    for index in (1, 2):
        ET.SubElement(content_types, f"{{{CONTENT_NS}}}Override", {
            "PartName": f"/xl/worksheets/sheet{index}.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        })

    parts = {
        "[Content_Types].xml": ET.tostring(content_types, encoding="utf-8", xml_declaration=True),
        "_rels/.rels": ET.tostring(package_relationships, encoding="utf-8", xml_declaration=True),
        "xl/workbook.xml": ET.tostring(workbook, encoding="utf-8", xml_declaration=True),
        "xl/_rels/workbook.xml.rels": ET.tostring(workbook_relationships, encoding="utf-8", xml_declaration=True),
        "xl/worksheets/sheet1.xml": _worksheet_xml(
            booking_rows, (24, 30, 20, 28, 22, 58, 18, 22, 22, 18, 26, 26), "L"
        ),
        "xl/worksheets/sheet2.xml": _worksheet_xml(summary_rows, (32, 24), "B"),
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def generate_daily_report(report_date=None):
    if report_date is None:
        report_date = datetime.date.today()
    elif isinstance(report_date, str):
        report_date = datetime.date.fromisoformat(report_date)
    report_date = report_date.isoformat()

    try:
        with sqlite3.connect(DATABASE_URL) as db:
            db.row_factory = sqlite3.Row
            bookings = db.execute(
                "SELECT * FROM bookings WHERE date(created_at) = ? ORDER BY created_at, id",
                (report_date,),
            ).fetchall()
    except sqlite3.Error as error:
        print(f"Database error: {error}")
        return False

    records = [_booking_record(booking) for booking in bookings]
    customer_keys = {
        record["customer_email"].strip().casefold()
        if record["customer_email"] != NOT_RECORDED
        else f"booking:{record['booking_id']}"
        for record in records
    }
    successful = [record for record in records if record["status_group"] == "successful"]
    failed = [record for record in records if record["status_group"] == "failed"]
    pending = [record for record in records if record["status_group"] == "pending"]
    summary = {
        "Total customers": len(customer_keys),
        "Total bookings": len(records),
        "Successful payments": len(successful),
        "Failed/cancelled payments": len(failed),
        "Pending/other payments": len(pending),
        "Total successful revenue": sum(record["total_amount"] for record in successful),
    }

    email_lines = [f"Daily Booking Report - {report_date}", "=" * 60, ""]
    if not records:
        email_lines.extend(["No bookings were recorded for this date.", ""])
    for index, record in enumerate(records, 1):
        email_lines.extend([
            f"Customer {index}",
            f"Name: {record['customer_name']}",
            f"Email: {record['customer_email']}",
            f"Phone: {record['customer_phone']}",
            f"Booking ID: {record['booking_id']}",
            f"Booking date and time: {record['booking_datetime']}",
            "",
            "Booked Items:",
            f"- {record['item_line']}",
            "",
            f"Total booking amount: ₹{record['total_amount']:,.2f}",
            f"Payment Status: {record['payment_status']}",
            f"Razorpay Order ID: {record['razorpay_order_id']}",
            f"Razorpay Payment ID: {record['razorpay_payment_id']}",
            "-" * 40,
            "",
        ])

    email_lines.extend(["DAILY SUMMARY", "=" * 40])
    email_lines.extend(f"{label}: {value}" for label, value in summary.items())
    email_body = "\n".join(email_lines)
    workbook_bytes = _create_workbook(records, summary)
    attachment = (
        f"booking_report_{report_date}.xlsx",
        base64.b64encode(workbook_bytes).decode("ascii"),
        EXCEL_CONTENT_TYPE,
    )

    print(f"Sending daily report for {report_date}...")
    sent = send_email(
        to=ADMIN_EMAIL,
        subject=f"Daily Booking Report - {report_date}",
        body=email_body,
        attachment=attachment,
    )
    if sent:
        print("Daily report sent successfully!")
    else:
        print("Failed to send daily report. Check email configuration.")
    return sent


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    generate_daily_report(target_date)
