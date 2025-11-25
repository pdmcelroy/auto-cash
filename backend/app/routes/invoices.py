"""
Invoice search and retrieval routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.netsuite_service import NetSuiteService
from app.models.schemas import InvoiceMatch

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

netsuite_service = NetSuiteService()


@router.get("/search")
async def search_invoices(
    invoice_number: Optional[str] = Query(None),
    customer_name: Optional[str] = Query(None),
    amount: Optional[float] = Query(None),
    limit: int = Query(10, ge=1, le=50)
):
    """Search for invoices in NetSuite"""
    if not any([invoice_number, customer_name, amount]):
        raise HTTPException(status_code=400, detail="At least one search parameter required")
    
    try:
        results = []
        
        if invoice_number:
            invoices = netsuite_service.search_invoices_by_number(invoice_number, limit=limit)
            results.extend(invoices)
        
        if customer_name:
            invoices = netsuite_service.search_invoices_by_customer(customer_name, limit=limit)
            results.extend(invoices)
        
        if amount:
            invoices = netsuite_service.search_invoices_by_amount(amount, tolerance=0.01, limit=limit)
            results.extend(invoices)
        
        # Remove duplicates by invoice_id
        seen = set()
        unique_results = []
        for invoice in results:
            if invoice["invoice_id"] not in seen:
                seen.add(invoice["invoice_id"])
                unique_results.append(invoice)
        
        return {"invoices": unique_results[:limit]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching invoices: {str(e)}")


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Get a specific invoice by ID"""
    try:
        invoice = netsuite_service.get_invoice(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving invoice: {str(e)}")

