# 🏢 MERCON Logistics — Drivers & Vehicles Bulk Excel Import Guide

This document provides a comprehensive guide for importing **Drivers** and **Vehicles (with Trailers)** into the MERCON Web Application. It contains instructions for company owners, fleet managers, and developers.

---

## 📂 Downloadable Templates Created

The following ready-to-use Excel (`.xlsx`) and CSV (`.csv`) files have been generated and stored in `docs/templates/` and `frontend/public/templates/`:

| File Name | Description | File Format |
|---|---|---|
| 📄 `MERCON_Master_Fleet_Import_Template.xlsx` | **All-in-One Workbook** containing Instructions, Drivers sheet, Vehicles sheet, and Reference values | `.xlsx` |
| 👨‍✈️ `MERCON_Drivers_Import_Template.xlsx` | **Drivers Only Template** pre-formatted with dropdowns and sample data | `.xlsx` |
| 🚛 `MERCON_Vehicles_Import_Template.xlsx` | **Vehicles & Trailers Template** pre-formatted with dropdowns and sample data | `.xlsx` |
| 📑 `MERCON_Drivers_Import_Template.csv` | Standard CSV import format for Drivers | `.csv` |
| 📑 `MERCON_Vehicles_Import_Template.csv` | Standard CSV import format for Vehicles | `.csv` |

---

## 👨‍✈️ 1. Drivers Data Template Structure

### Columns & Field Specifications

| Column Name | Required? | Field Type | Validation / Allowed Values | Description & Example |
|---|---|---|---|---|
| **Driver Ref / ID** | Optional | Text | Unique ID string | Internal identifier or legacy ID (e.g. `DRV-101`). Auto-generated if left empty. |
| **First Name \*** | **Required** | Text | String | Driver's legal first name (e.g. `Ahmed`). |
| **Last Name \*** | **Required** | Text | String | Driver's legal last name / family name (e.g. `Al-Mansoor`). |
| **Primary Phone \*** | **Required** | Text | Unique Phone String | Primary contact phone number (e.g. `+966 50 123 4567`). Must be unique in system. |
| **License Number \*** | **Required** | Text | String | Official driver's license number (e.g. `DL-98765432`). |
| **License Expiry Date \*** | **Required** | Date | `YYYY-MM-DD` | Expiry date of driving license (e.g. `2028-12-31`). |
| **Assigned Vehicle Plate** | Optional | Text | Registration Plate | License plate number of assigned vehicle (e.g. `8492-RKA`). |

*(Note: Imported drivers default automatically to `Available` status in MERCON).*

---

## 🚛 2. Vehicles & Trailers Data Template Structure

### Columns & Field Specifications

| Column Name | Required? | Field Type | Validation / Allowed Values | Description & Example |
|---|---|---|---|---|
| **Vehicle Ref / ID** | Optional | Text | Unique ID string | Internal vehicle code (e.g. `TRK-101`). Auto-generated if left empty. |
| **Plate Number \*** | **Required** | Text | Unique License Plate | Official vehicle registration plate (e.g. `8492-RKA` or `ABC-1234`). |
| **Asset Type \*** | **Required** | Dropdown | `Flatbed`, `Reefer`, `Box`, `Tanker` | Primary vehicle body/asset type. |
| **Capacity (KG) \*** | **Required** | Numeric | Positive Integer | Maximum weight payload capacity in Kilograms (e.g. `25000`). |
| **Current Odometer (KM)** | Optional | Numeric | Decimal / Float | Current odometer reading in KM (e.g. `45000.0`). |
| **ICCES Device ID** | Optional | Text | ICCES Device ID String | Unique ICCES GPS Device ID assigned to this truck (e.g. `06670881` or `351777090213198`). |
| **Assigned Driver Phone / Name** | Optional | Text | Phone or Name String | Phone number or name of assigned driver (e.g. `+966 50 123 4567` or `Ahmed Al-Mansoor`). |
| **Trailer Number** | Optional | Text | String | Linked trailer identifier (e.g. `TRL-402`). |
| **Trailer Capacity (KG)** | Optional | Numeric | Positive Integer | Linked trailer payload capacity in KG (e.g. `30000`). |

*(Note: Imported vehicles default automatically to `Available` status in MERCON).*

---

## ⚙️ 3. Developer & Backend API Import Schema Mapping

When processing the Excel file via backend parser (Node.g. `xlsx` or `exceljs`), map columns to Prisma database models as follows:

### Driver Model Mapping
```json
{
  "ref_id": "Driver Ref / ID or auto-generated",
  "first_name": "First Name *",
  "last_name": "Last Name *",
  "phone_primary": "Primary Phone *",
  "license_number": "License Number *",
  "license_expiry": "License Expiry Date * (ISO-8601 DateTime)",
  "status": "Status (Enum: Available | OnTrip | OffDuty | Inactive)"
}
```

### Vehicle Model Mapping
```json
{
  "ref_id": "Vehicle Ref / ID or auto-generated",
  "plate_number": "Plate Number *",
  "asset_type": "Asset Type * (Enum: Flatbed | Reefer | Box | Tanker)",
  "capacity_kg": "Capacity (KG) * (Integer)",
  "status": "Status (Enum: Available | OnTrip | Maintenance | Inactive)",
  "current_odometer": "Current Odometer (KM) (Float)",
  "gps_device_id": "GPS Device ID",
  "icces_device_id": "ICCES Device ID",
  "trailer_number": "Trailer Number",
  "trailer_type": "Trailer Type (Enum: Flatbed | Reefer | Box | Tanker)",
  "trailer_capacity_kg": "Trailer Capacity (KG) (Integer)"
}
```

---

## 💡 Instructions to Give to the Client Company Owner

1. **Download the File**: Share `MERCON_Master_Fleet_Import_Template.xlsx` (or separate Driver & Vehicle files).
2. **Review Sample Data**: Rows 5–7 contain sample entries to illustrate expected formatting. These can be edited or overwritten.
3. **Use Dropdowns**: For fields like *Asset Type* and *Status*, select values directly from the dropdown arrow in Excel.
4. **Mandatory Fields**: Ensure all columns marked with an asterisk (`*`) are completed.
5. **Return File**: Return the completed `.xlsx` file to the MERCON team for direct system import.
