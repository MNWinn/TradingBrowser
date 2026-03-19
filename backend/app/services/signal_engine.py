from app.services.swarm import SwarmOrchestrator


class EnsembleSignalEngine:
    def __init__(self):
        self.orchestrator = SwarmOrchestrator()

    async def generate(self, ticker: str, mode: str) -> dict:
        swarm = await self.orchestrator.run(ticker=ticker, mode=mode)
        action = swarm["aggregated_recommendation"]
        confidence = 0.5 + (swarm["consensus_score"] * 0.4) - (swarm["disagreement_score"] * 0.2)
        confidence = max(min(confidence, 0.99), 0.01)

        return {
            "ticker": ticker,
            "action": action,
            "confidence": round(confidence, 2),
            "consensus_score": swarm["consensus_score"],
            "disagreement_score": swarm["disagreement_score"],
            "position_size_suggestion": 1000.0 if action in {"LONG", "SHORT"} else 0.0,
            "stop_loss": 0.02 if action in {"LONG", "SHORT"} else None,
            "target": 0.04 if action in {"LONG", "SHORT"} else None,
            "reason_codes": ["SWARM_ENSEMBLE", "MIROFISH_INCLUDED", f"MODE_{mode.upper()}"],
            "explanation": f"Action {action} based on multi-agent consensus with MiroFish context.",
            "execution_eligibility": {
                "research": False,
                "paper": action in {"LONG", "SHORT"},
                "live": False,
            },
            "swarm": swarm,
        }
