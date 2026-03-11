import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects
from ...models import AutoScanInput, CampaignCreate, ProspectInput, ProspectScanInput
from ...scan import create_campaign, scan_prospects, load_csv

router = APIRouter(prefix="/api", tags=["Campaign"])


@router.post("/campaign/create")
def api_create(data: CampaignCreate, db: Session = Depends(get_db)):
    c = create_campaign(db, data)
    return {"campaign_id": c.campaign_id, "profession": c.profession, "city": c.city, "mode": c.mode}


@router.get("/campaign/{cid}/status")
def api_status(cid: str, db: Session = Depends(get_db)):
    c = db_get_campaign(db, cid)
    if not c: raise HTTPException(404, "Campagne introuvable")
    ps = db_list_prospects(db, cid)
    counts = {}
    for p in ps: counts[p.status] = counts.get(p.status, 0) + 1
    return {"campaign_id": cid, "profession": c.profession, "city": c.city,
            "total": len(ps), "by_status": counts, "eligible": sum(1 for p in ps if p.eligibility_flag)}


@router.get("/campaigns")
def api_list(db: Session = Depends(get_db)):
    return [{"campaign_id": c.campaign_id, "profession": c.profession, "city": c.city,
             "mode": c.mode, "prospects": len(c.prospects)} for c in db_list_campaigns(db)]


@router.post("/prospect-scan")
def api_scan(data: ProspectScanInput, db: Session = Depends(get_db)):
    try: ps = scan_prospects(db, data)
    except ValueError as e: raise HTTPException(400, str(e))
    return {"campaign_id": ps[0].campaign_id if ps else None, "created": len(ps),
            "prospects": [{"id": p.prospect_id, "name": p.name, "status": p.status} for p in ps]}


@router.post("/prospect-scan/auto")
def api_scan_auto(data: AutoScanInput, db: Session = Depends(get_db)):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(400, "GOOGLE_MAPS_API_KEY manquante — ajoutez-la dans votre .env")

    from ...google_places import search_prospects_enriched
    try:
        raw, reasons = search_prospects_enriched(data.profession, data.city, api_key, data.max_prospects)
    except ValueError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Erreur Google Places API: {exc}")

    if data.campaign_id:
        campaign = db_get_campaign(db, data.campaign_id)
        if not campaign:
            raise HTTPException(404, f"Campagne {data.campaign_id} introuvable")
    else:
        campaign = create_campaign(db, CampaignCreate(
            profession=data.profession, city=data.city, max_prospects=data.max_prospects))

    manual = [ProspectInput(name=p["name"], website=p["website"],
                            phone=p.get("tel"), reviews_count=p["reviews_count"])
              for p in raw]
    scan_data = ProspectScanInput(city=data.city, profession=data.profession,
                                  max_prospects=data.max_prospects,
                                  campaign_id=campaign.campaign_id,
                                  manual_prospects=manual)
    try:
        ps = scan_prospects(db, scan_data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    # Enregistrer mobile, cms, email directement sur les ProspectDB créés
    raw_by_website = {p["website"]: p for p in raw}
    for prospect in ps:
        enriched = raw_by_website.get(prospect.website or "")
        if enriched:
            if enriched.get("mobile"):
                prospect.mobile = enriched["mobile"]
            if enriched.get("cms"):
                prospect.cms = enriched["cms"]
            if enriched.get("email") and not prospect.email:
                prospect.email = enriched["email"]
    db.commit()

    return {
        "campaign_id": campaign.campaign_id,
        "created":     len(ps),
        "skipped":     len(reasons),
        "reasons":     reasons,
        "source":      "google_places",
        "prospects":   [
            {
                "id":      p.prospect_id,
                "name":    p.name,
                "website": p.website,
                "tel":     p.phone,
                "mobile":  p.mobile,
                "email":   p.email,
                "cms":     p.cms,
            }
            for p in ps
        ],
    }


@router.post("/prospect-scan/csv")
async def api_scan_csv(city: str, profession: str, max_prospects: int = 30,
                       campaign_id: str = None, file: UploadFile = File(...),
                       db: Session = Depends(get_db)):
    content = (await file.read()).decode("utf-8")
    manual = load_csv(content, city, profession)
    if not manual: raise HTTPException(400, "CSV vide ou colonne 'name' absente")
    data = ProspectScanInput(city=city, profession=profession, max_prospects=max_prospects,
                             campaign_id=campaign_id, manual_prospects=manual[:max_prospects])
    try: ps = scan_prospects(db, data)
    except ValueError as e: raise HTTPException(400, str(e))
    return {"created": len(ps), "campaign_id": ps[0].campaign_id if ps else None}
