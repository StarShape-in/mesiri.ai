# MERCON Logistics — Business Rules

Version: 1.1 (Unified)  
Date: July 2026  
Prepared For: MERCON Logistics Services Company  

## Overview
These business rules define the operational logic and constraints that govern the MERCON Logistics platform, ensuring consistency, data integrity, and a standardized experience across the Driver Operations App, Operator Mobile App, Operator Web Dashboard, and Admin Web Dashboard.

---

### BR-001 · User Authentication & Access Control
| Rule | Description |
| :--- | :--- |
| BR-001.1 | Every user must authenticate using authorized credentials before accessing the system |
| BR-001.2 | Admin & Operator authenticate using Email + Password |
| BR-001.3 | Drivers authenticate using Primary Mobile Number + License Number (PIN equivalent) |
| BR-001.4 | Users shall only have access to modules permitted by their assigned role |
| BR-001.5 | Sessions must automatically expire after prolonged inactivity |
| BR-001.6 | All user activities shall be recorded in the audit log |
| BR-001.7 | JWT-based authentication with role-based access control enforced across all applications |

### BR-002 · Driver Assignment
| Rule | Description |
| :--- | :--- |
| BR-002.1 | A driver may only have one active trip at any given time |
| BR-002.2 | Only drivers marked as Available may be assigned to a trip |
| BR-002.3 | Drivers cannot manually assign or modify trips |
| BR-002.4 | Assignments become immediately available in the Driver App |

### BR-003 · Vehicle Assignment
| Rule | Description |
| :--- | :--- |
| BR-003.1 | A vehicle may only be assigned to one active trip at a time |
| BR-003.2 | Vehicles under maintenance cannot be assigned |
| BR-003.3 | Vehicles with expired documentation are unavailable for assignment |
| BR-003.4 | Only vehicles with sufficient capacity may be assigned to the selected cargo |

### BR-004 · Trip Creation
| Rule | Description |
| :--- | :--- |
| BR-004.1 | Every trip must be associated with a registered customer |
| BR-004.2 | Pickup and delivery locations are mandatory |
| BR-004.3 | Cargo information must be completed before a trip can be created |
| BR-004.4 | A driver and vehicle must be assigned before trip status becomes Assigned |
| BR-004.5 | Each trip shall have a unique Trip ID |
| BR-004.6 | Trips can be created from both the Operator Web Dashboard and Operator Mobile App |

### BR-005 · Pricing & Quotations
| Rule | Description |
| :--- | :--- |
| BR-005.1 | The system shall automatically suggest pricing based on predefined route rates |
| BR-005.2 | Operators may manually override the suggested price |
| BR-005.3 | Customer-specific pricing takes precedence over default pricing |
| BR-005.4 | Invoicing calculates flat subtotal and generates final invoice automatically upon trip completion |

### BR-006 · Driver Workflow
| Rule | Description |
| :--- | :--- |
| BR-006.1 | If an active trip exists, the Driver App opens directly to the current trip |
| BR-006.2 | Driver taps "Start Trip" to initiate the pre-departure checklist |
| BR-006.3 | Drivers cannot proceed without completing mandatory cargo photo verification |
| BR-006.4 | Trip status changes to In Transit after cargo photos are successfully uploaded |
| BR-006.5 | The navigation screen automatically opens after the trip begins |

### BR-007 · GPS Tracking
| Rule | Description |
| :--- | :--- |
| BR-007.1 | Driver mobile GPS is the primary source of live location tracking |
| BR-007.2 | ICCES vehicle GPS functions as a secondary tracking source when available |
| BR-007.3 | GPS tracking begins automatically when a trip starts and ends when it completes |
| BR-007.4 | Location updates synchronize continuously with the Operator Dashboard |
| BR-007.5 | **(NEW)** Location updates are streamed using low-latency WebSockets (Socket.io) directly to the Live Tracking Map every 10 seconds |

### BR-008 · Emergency Handling
| Rule | Description |
| :--- | :--- |
| BR-008.1 | Drivers may report emergencies at any time during an active trip |
| BR-008.2 | Emergency alerts shall immediately notify the assigned operator |
| BR-008.3 | The driver's live GPS location shall accompany every emergency report |
| BR-008.4 | Trip status changes to Emergency / Halted |

### BR-009 · Arrival & Delivery Verification
| Rule | Description |
| :--- | :--- |
| BR-009.1 | The application shall detect arrival using GPS geofencing (default radius: 500 meters) |
| BR-009.2 | Delivery photographs (POD) are mandatory before completing a trip |
| BR-009.3 | Trip status changes to Completed after successful delivery verification |

### BR-010 · Operations & Fleet Management
| Rule | Description |
| :--- | :--- |
| BR-010.1 | Operators may assign or reassign drivers before a trip starts |
| BR-010.2 | Every truck shall have a unique fleet record with merged trailer capabilities |
| BR-010.3 | Maintenance schedules and external workshop receipts shall be recorded for every vehicle |

### BR-011 · Security & Audit
| Rule | Description |
| :--- | :--- |
| BR-011.1 | All critical system actions shall be logged via timestamps and user tracking |
| BR-011.2 | Role-based permissions shall be enforced across all applications |
| BR-011.3 | Deleted records remain recoverable via Soft Delete architecture |
