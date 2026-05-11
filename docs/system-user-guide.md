# GMI Terralink System User Guide

This guide explains how daily users work inside the GMI Terralink system. It covers the main modules, business workflows, document handling, payments, reports, notifications, and role-based permissions for the operational teams.

## 1. What the System Does

The system supports GMI Terralink's logistics, sourcing, invoicing, payment, warehouse, and reporting operations in one place. It keeps customer records, cargo records, sourcing transactions, supplier records, invoices, receipts, purchase orders, transit updates, delivery records, and financial summaries connected to the right business workflow.

The system separates two major lanes:

- **Logistics lane:** cargo intake, loadings, freight billing, freight payments, transit tracking, container return, proof of delivery, and closed loading history.
- **Sourcing / Trade lane:** customer inquiries, uploaded documents, Q-Worksheets, supplier sourcing, proformas, final invoices, client payments, purchase orders, supplier payments, inventory, fulfillment, proof of delivery, and closed trade history.

Users only see and use the modules allowed for their role.

## 2. User Roles and Permissions

| Role | Main Responsibility | Typical Access |
| --- | --- | --- |
| Director | Business oversight, approvals, reports, high-level finance visibility, closed trade control | Dashboards, clients, logistics, sourcing, finance summaries, reports, payment ledgers, approvals, locked or closed record review |
| Finance Officer | Payment control, invoices, receipts, client payments, freight payments, payment verification | Payment ledgers, receipts, finance actions, invoice payment recording, payment reports |
| Procurement Officer | Sourcing, supplier management, Q-Worksheets, purchase orders, supplier payments, fulfillment support | Sourcing / Trade lane, suppliers, Q-Worksheets, sourcing invoices, purchase orders, supplier payment records, inventory and fulfillment workflows |
| Office Intake User | Daily intake and operations capture | Clients, cargo intake, loading records, documents, workflow updates, delivery support, and operational tracking where permitted |

### Permission Rules Users Should Know

- If a menu item is not visible or a page says permission is required, the user's role does not allow that action.
- Payment recording is controlled by Finance. Users outside Finance may need to request Finance approval before a payment can be recorded.
- Closed trade records are protected. Reopening or editing a closed trade requires Director-level approval and a clear reason.
- Procurement and sourcing actions are handled by Procurement users and the Director.
- Reports and business-wide finance summaries are reserved for Director-level review.
- Users should not share login accounts. Every action is tracked against the signed-in user.

## 3. Getting Started

1. Open the system link provided by the company.
2. Sign in with your username and password.
3. Check the sidebar for the modules available to your role.
4. Use the lane switcher to move between Logistics and Sourcing where your role allows it.
5. Watch the notification icon for assigned tasks, approvals, payment updates, and workflow changes.

## 4. How to Train Yourself With This Manual

Use this guide as a practical training path, not only as a reference document. A new user should go through the sections in order and practise with sample records or supervised live records.

Recommended training order:

1. **Understand your role:** Read the role and permission table first so you know which modules apply to you.
2. **Learn the layout:** Open the dashboard, sidebar, lane switcher, notifications, and user menu.
3. **Practise navigation:** Open each module available to your role and identify list pages, detail pages, create buttons, filters, and search boxes.
4. **Follow one workflow at a time:** Start with either Logistics or Sourcing. Do not jump between both until the first workflow is clear.
5. **Review documents carefully:** Open proformas, final invoices, receipts, and previews before saving or printing.
6. **Check permissions:** If an action is blocked, note the required role or approval path instead of trying to force the action.
7. **Use the practice checklists:** Complete the checklists in this guide until you can perform the steps without help.

Training rule: never practise with a real customer record unless your supervisor has confirmed it is safe to use. If test records are available, use those first.

## 5. Dashboard

The dashboard is the starting point after login. It gives a quick view of operational activity and helps users move to pending work.

Common dashboard uses:

- Review recent client, cargo, payment, or sourcing activity.
- Open notifications linked to records requiring attention.
- Move quickly to logistics or sourcing workflows.
- Check status indicators for active work.

## 6. Client Directory

The client module stores customer information used across logistics and sourcing.

Typical client details include:

- Client name and company name
- Contact person
- Phone and email
- Address and country
- Notes or remarks
- Linked cargo, transactions, invoices, and payment history

Good client data matters because invoices, receipts, delivery records, and reports depend on it.

## 7. Logistics Lane

The Logistics lane handles cargo and freight operations.

### Cargo Intake and Loading Records

Users record cargo details such as:

- Client
- Cargo description
- Entry type
- Weight and package information
- Container number and container size where applicable
- Origin, destination, route, and shipment notes
- Loading status and operational dates

Container numbers are normalized and validated, so users should enter them carefully.

### Cargo Documents

Cargo documents include proforma invoices and final invoices for freight-related billing. These documents use the GMI document format and can be opened in preview mode.

To save a document as PDF:

1. Open the proforma, final invoice, or receipt.
2. Click **Download PDF**.
3. The browser print dialog opens.
4. Choose **Save as PDF**.

This method ensures the saved PDF matches the print preview.

### Transit Tracking

Transit records help teams monitor movement after dispatch.

Transit information may include:

- Vessel or movement reference
- Departure and arrival dates
- Current status
- Route details
- Next steps and operational notes

Users should update transit records when the cargo moves to the next stage.

### Freight Payments and Receipts

Freight payment actions are linked to cargo invoices. Finance users record payment details, and the system can generate receipts.

Receipts can be previewed, signed where applicable, and saved as PDF through browser print.

### Proof of Delivery and Container Return

Proof of Delivery records confirm that cargo reached the receiver. Container return records help track container status after delivery.

Users should capture accurate dates, receiver details, return status, and supporting notes.

## 8. Sourcing / Trade Lane

The Sourcing / Trade lane handles customer buying requests, supplier sourcing, invoicing, purchase orders, fulfillment, and delivery.

### Trade Transactions

A trade transaction represents a customer sourcing request. It may begin from manual entry or from an uploaded customer document.

Common transaction stages include:

- Inquiry received
- Details reviewed
- Sourcing in progress
- Proforma prepared
- Customer confirmed
- Payment received or partially received
- Purchase order created
- Supplier purchase in progress
- Fulfillment and delivery
- Closed

The transaction status board helps users see the next action needed for each trade.

### Document Upload and Extraction

Users can upload customer documents such as inquiry files, proforma references, or supporting trade documents. The system stores extracted text and structured data where available.

Good practice:

- Upload clear documents.
- Review extracted details before creating sourcing records.
- Keep document records linked to the correct transaction.

### Q-Worksheets

Q-Worksheets are used for supplier quote work. They help Procurement users convert customer requirements into supplier options, costs, margins, resale pricing, and notes.

Q-Worksheet work may include:

- Product or item description
- Supplier details
- Cost price
- Resale price
- Quantity
- Margin or service fee review
- Notes for sourcing decisions

### Suppliers and Supplier Products

Supplier records store supplier contact details, products, minimum order quantities, pricing references, and notes. Procurement users use these records to support future sourcing and purchase decisions.

### Sourcing Billing

Sourcing billing includes proforma invoices and final invoices for trade transactions. These documents remain separate from logistics freight billing.

Important rule:

- Sourcing charges stay in sourcing invoices.
- Logistics freight charges stay in logistics invoices.

### Client Payments

Client payments are recorded against confirmed sourcing invoices. Finance users handle payment records and receipts. Payment status affects whether Procurement can proceed with purchase order and fulfillment steps.

### Purchase Orders

Purchase orders are used for sourcing/procurement work after the customer confirms and the payment requirements are satisfied.

Purchase order records may show:

- Supplier allocation
- Related final invoice
- Purchase lines
- Fulfillment readiness
- Supplier payment status
- Parent and child purchase order relationships where used

### Supplier Payments

Supplier payments track money paid out to suppliers against purchase orders. These records help separate customer receipts from supplier costs.

### Inventory and Fulfillment

Inventory and fulfillment workflows help track sourced goods through storage, allocation, shipment, port movement, inland delivery, and proof of delivery.

Users should update fulfillment records as items move through the process so the transaction remains accurate.

## 9. Payments Ledger

The payments ledger gives Finance and Director-level users visibility into recorded payments. It helps users review payment history, balances, receipt status, and linked documents.

Payment records should include:

- Correct client or transaction
- Payment method
- Amount paid
- Currency
- Payment date
- Notes or reference number
- Linked final invoice where applicable

If a user cannot record a payment, they should use the available request path or ask Finance to complete the entry.

## 10. Receipts

Receipts confirm money received from clients. The system supports receipts for logistics and sourcing payments.

Receipt workflow:

1. Payment is recorded.
2. Receipt is generated.
3. Receipt can be reviewed and signed where applicable.
4. User clicks **Download PDF**.
5. Browser print opens and the user saves as PDF.

Receipt reversals or refunds are controlled actions and should include a proper reason.

## 11. Reports

Reports help authorized users review operational and financial performance.

Available reporting areas may include:

- Revenue and outstanding balances
- Client activity
- Shipment activity
- Payment reports
- Sourcing reports
- Final invoice reports
- Trade payment reports
- Director finance summary

Reports should be used for management review, reconciliation, and operational follow-up.

## 12. Notifications

Notifications guide users to items that need action.

Examples:

- A payment needs Finance attention.
- A document was generated or signed.
- A transaction moved to the next stage.
- A workflow item needs review.
- A user opened a linked task and the unread badge clears automatically.

Users should treat notifications as task prompts and open them regularly.

## 13. Document Signing and PDF Saving

Some documents can carry an authorized signature. Users should check the preview before saving or sending documents.

For proformas, final invoices, and receipts:

1. Open the document detail page.
2. Review the embedded preview.
3. Sign if the workflow requires it and your role allows it.
4. Click **Download PDF**.
5. In the browser print dialog, select **Save as PDF**.

## 14. Closed Records

Closed records protect completed work from accidental changes.

Closed logistics or trade records may limit editing. If a record must be reopened, users should provide a clear business reason and follow the approval path.

Examples of why a record may need review:

- Incorrect amount entered
- Missing payment reference
- Wrong client linked
- Delivery update required
- Document correction requested

## 15. Self-Training Workflows

The workflows below are designed for new users to practise the system from beginning to end. Work slowly, read each page before saving, and confirm that the record moved to the expected next stage.

### Workflow A: Learn the Dashboard and Navigation

Goal: become comfortable moving around the system.

1. Sign in.
2. Open the dashboard.
3. Read the activity cards and recent records.
4. Open the sidebar and identify the modules available to your role.
5. Use the lane switcher to move between Logistics and Sourcing if your role allows both.
6. Open the notification dropdown and review any unread notifications.
7. Return to the dashboard.

You are ready for the next workflow when you can explain where to find clients, cargo, transactions, payments, receipts, and reports available to your role.

### Workflow B: Create or Review a Client

Goal: understand how customer records support all other work.

1. Open **Clients**.
2. Search for the customer name before creating a new record.
3. If the client exists, open the detail page and review contact information.
4. If you are allowed to create clients, add a new client with name, company, contact person, phone, email, address, country, and notes.
5. Save the record.
6. Reopen the client and confirm the information is correct.

Training check: the client should be easy to identify and should not duplicate an existing customer.

### Workflow C: Logistics Cargo Intake to Freight Document

Goal: practise the cargo intake and billing preparation path.

1. Switch to the Logistics lane.
2. Open **Cargo / Loadings**.
3. Create or open a loading record.
4. Confirm the client, cargo description, weight, package details, origin, destination, and route.
5. Add container details where applicable.
6. Save the cargo record.
7. Open the cargo detail page and review status, notes, and next action.
8. Open the related cargo document area.
9. Review the proforma or final invoice preview.
10. Use **Download PDF** and choose **Save as PDF** from the browser print dialog.

Training check: the document should show the correct client, cargo details, totals, and GMI formatting.

### Workflow D: Logistics Transit and Delivery Follow-Up

Goal: practise updating movement after cargo has been loaded or dispatched.

1. Open **Transit**.
2. Find the shipment or cargo movement record.
3. Review current status, route, departure details, and arrival details.
4. Add movement notes or next-step updates where allowed.
5. Save the transit update.
6. Open Proof of Delivery when delivery is complete.
7. Capture receiver details and delivery notes where required.
8. Check whether container return tracking is needed.

Training check: the cargo status should clearly show where the shipment is and what action remains.

### Workflow E: Sourcing Inquiry to Q-Worksheet

Goal: practise converting a customer request into sourcing work.

1. Switch to the Sourcing / Trade lane.
2. Open **Transactions**.
3. Create or open a customer sourcing transaction.
4. Confirm the client, requested items, notes, and source documents.
5. Upload supporting inquiry documents where available.
6. Open **Q-Worksheets**.
7. Create or update worksheet lines for supplier options, cost price, resale price, quantity, and notes.
8. Save the worksheet.
9. Return to the transaction and confirm the next action.

Training check: another user should be able to understand what the customer requested and what supplier option is being considered.

### Workflow F: Sourcing Billing to Client Payment

Goal: understand how sourcing invoices and client payments connect.

1. Open the sourcing transaction.
2. Review the proforma invoice.
3. Confirm that sourcing fees and item charges are in the sourcing document only.
4. Generate or open the final invoice when the transaction is ready.
5. Review invoice totals, currency, balance, and payment status.
6. If you are a Finance user, record the client payment against the correct invoice.
7. If you are not a Finance user, request Finance support where the system requires it.
8. Open the receipt and save it as PDF through the browser print dialog.

Training check: the final invoice, payment, balance, and receipt should all refer to the same client transaction.

### Workflow G: Purchase Order and Supplier Payment

Goal: practise procurement follow-up after customer confirmation and payment readiness.

1. Open **Purchase Orders**.
2. Find the purchase order linked to the sourcing transaction.
3. Review supplier, items, quantities, costs, and linked invoice.
4. Confirm whether procurement is ready to continue.
5. Update supplier allocation or purchase details where allowed.
6. Open **Supplier Payments** when a supplier payment must be recorded.
7. Confirm the purchase order, supplier, amount, currency, and notes before saving.

Training check: supplier payments should never be confused with client receipts.

### Workflow H: Inventory, Fulfillment, and Delivery

Goal: practise tracking sourced goods after purchase.

1. Open **Inventory** and confirm whether the item is in stock, allocated, or moving.
2. Open **Fulfillment** and review shipment or delivery stages.
3. Update warehouse allocation, port movement, inland delivery, or delivery notes where allowed.
4. Create or update Proof of Delivery once goods reach the receiver.
5. Return to the transaction and confirm the status reflects the completed work.

Training check: the transaction should show a clear trail from customer request to delivery.

### Workflow I: Reports and Reconciliation Review

Goal: learn how users with reporting access review performance and exceptions.

1. Open **Reports** if your role allows it.
2. Review revenue, outstanding balances, activity, payments, invoices, and sourcing summaries.
3. Compare report totals with payment ledgers and invoice lists.
4. Identify records that need correction, follow-up, or explanation.
5. Do not change financial records without confirming the correct source document.

Training check: you should be able to explain which records make up a report total.

### Workflow J: Handling a Blocked Action

Goal: understand what to do when your role cannot complete an action.

1. Read the permission message on the page.
2. Confirm whether the action belongs to Finance, Procurement, or Director review.
3. Use the available request path if the system provides one.
4. Add clear notes explaining what action is needed.
5. Notify the responsible team member with the record reference.
6. Wait for the authorized user to complete or approve the action.

Training check: the request should clearly explain the record, the needed action, and the business reason.

## 16. Training Checklists by Role

### Director Checklist

- Open the dashboard and review active operations.
- Open the payment ledger and confirm balances.
- Open reports and review revenue, outstanding balances, and activity summaries.
- Review a closed trade record and understand when reopening is appropriate.
- Open a sourcing transaction and identify its next action.

### Finance Officer Checklist

- Open final invoices and identify paid, unpaid, and partially paid records.
- Record a payment against the correct invoice.
- Generate and review a receipt.
- Confirm the balance after payment.
- Review the payments ledger and payment reports.

### Procurement Officer Checklist

- Open a sourcing transaction and review customer requirements.
- Create or update a Q-Worksheet.
- Review supplier records and supplier products.
- Open a purchase order linked to a paid or ready transaction.
- Review supplier payment and fulfillment status.

### Office Intake User Checklist

- Search for an existing client before creating a new one.
- Capture cargo intake details accurately.
- Upload documents to the correct record.
- Update operational notes and workflow status where allowed.
- Identify when Finance, Procurement, or Director support is required.

## 17. Common Mistakes to Avoid During Training

- Creating duplicate clients instead of searching first.
- Mixing logistics charges into sourcing invoices.
- Mixing sourcing charges into logistics invoices.
- Recording payments against the wrong invoice or transaction.
- Saving a document before reviewing the preview.
- Uploading a document to the wrong client or transaction.
- Updating a closed record without approval.
- Treating supplier payments as client receipts.
- Ignoring notifications that point to pending work.

## 18. Good Working Practices

- Always search for an existing client before creating a new one.
- Keep logistics and sourcing workflows separate.
- Enter container numbers, invoice amounts, currencies, and payment references carefully.
- Upload documents to the correct transaction.
- Use notes to explain unusual changes.
- Review previews before saving PDFs.
- Do not record payments unless you are certain about the amount, currency, invoice, and client.
- Use notifications and status boards to follow next steps.
- Avoid sharing accounts; actions are linked to the user who performs them.

## 19. Quick Role Guide

### Director

- Reviews business performance and financial summaries.
- Oversees both logistics and sourcing operations.
- Reviews locked or closed trade changes.
- Can view payment ledgers and reports.
- Can support procurement review and sourcing oversight.

### Finance Officer

- Records and verifies client payments.
- Manages receipts and payment references.
- Reviews invoice balances and payment status.
- Handles freight and sourcing payment records where permitted.
- Supports payment-related reports.

### Procurement Officer

- Handles sourcing transactions and Q-Worksheets.
- Manages suppliers and supplier product information.
- Works with purchase orders and supplier payments.
- Supports inventory, fulfillment, and delivery tracking for sourced goods.
- Keeps sourcing billing separate from logistics billing.

### Office Intake User

- Captures client and cargo intake details.
- Supports loading, shipment, and operational updates.
- Uploads or reviews documents where permitted.
- Follows notifications and workflow prompts.
- Requests Finance or Director support where a restricted action is required.

## 20. When to Ask for Help

Ask for help when:

- A page says permission is required.
- A payment was entered incorrectly.
- A record is closed but needs correction.
- A document preview does not match the expected details.
- A transaction is stuck and the next action is unclear.
- A duplicate client, invoice, payment, or transaction appears.

Keeping records accurate is more important than moving fast. When in doubt, pause and request review before saving financial or closed-workflow changes.
