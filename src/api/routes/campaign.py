from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ...database import get_db, db_get_campaign, db_list_campaigns, db_list_prospects
from ...models import CampaignCreate, ProspectScanInput
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
