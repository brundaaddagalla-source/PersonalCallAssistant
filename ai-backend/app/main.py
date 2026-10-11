from fastapi import FastAPI

from app import __version__
from app.schemas import ClassifyRequest, ClassifyResponse, DecideRequest, Decision
from app.services import decision as engine

app = FastAPI(
    title="Personal Call Agent - AI Decision API",
    version=__version__,
    description="Classifies caller intent, scores spam/fraud risk, applies user rules and returns a structured decision.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/v1/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    """Intent + risk + identification only, no action."""
    return engine.classify(req.caller, req.transcript)


@app.post("/v1/decide", response_model=Decision)
def decide(req: DecideRequest) -> Decision:
    """Stateless: send the full transcript so far each turn; get the next action and what to say."""
    return engine.decide(req)
