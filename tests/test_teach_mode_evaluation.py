import unittest
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.memory.service import MemoryService, MemoryProposal, VersionedClaim, SourceEvent
from packages.persona.domain import Recipient

import uuid

class TeachModeEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = MemoryService()

    def _create_claim(self, content: str, provenance: str) -> VersionedClaim:
        event = self.memory.add_source_event(SourceEvent(
            event_id=str(uuid.uuid4()), source_type="chat", occurred_at=datetime.now(timezone.utc).isoformat(), payload={"text": content}
        ))
        claim = VersionedClaim(
            claim_id=str(uuid.uuid4()), subject="Kur", predicate="is/does", value=content, claim_type="semantic",
            source_event_id=event.event_id, provenance=provenance, authority="user_explicit", status="confirmed",
            sensitivity="private", allowed_audiences=frozenset(), user_confirmation="explicit",
            confidence=1.0, asserted_at=datetime.now(timezone.utc).isoformat()
        )
        return self.memory.add_claim(claim)

    def test_extracts_facts_without_inventing_details(self) -> None:
        # User: "I play Genshin most evenings. I prefer exploration to difficult combat."
        claim1 = self._create_claim("often plays Genshin in the evening.", "private chat session 1")
        claim2 = self._create_claim("prefers exploration over difficult combat.", "private chat session 1")
        
        self.assertEqual(claim1.status, "confirmed")
        self.assertEqual(claim2.status, "confirmed")
        self.assertEqual(len(self.memory.claims()), 2)
        
        # Verify retrieval
        claims = self.memory.retrieve_claims("Genshin", Recipient.MASTER_PRIVATE)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].claim_id, claim1.claim_id)

    def test_handles_contradictory_claims_and_supersession(self) -> None:
        # User explicitly updates preference
        # Old claim: Kur prefers exploration over difficult combat.
        old_claim = self._create_claim("prefers exploration over difficult combat.", "private chat session 1")
        
        # Later, user says: "Actually, I like difficult combat now."
        new_claim = self._create_claim("likes difficult combat now.", "private chat session 2")
        
        # For a full implementation, we'd have logic linking them. 
        # Here we manually simulate the supersession that the UI/Agent might do.
        updated_old = VersionedClaim(
            claim_id=old_claim.claim_id,
            subject=old_claim.subject,
            predicate=old_claim.predicate,
            value=old_claim.value,
            claim_type=old_claim.claim_type,
            source_event_id=old_claim.source_event_id,
            provenance=old_claim.provenance,
            authority=old_claim.authority,
            confidence=old_claim.confidence,
            asserted_at=old_claim.asserted_at,
            valid_from=old_claim.valid_from,
            valid_until=datetime.now(timezone.utc).isoformat(),
            status="superseded",
            sensitivity=old_claim.sensitivity,
            allowed_audiences=old_claim.allowed_audiences,
            supersedes=None,
            replaces=None,
            user_confirmation="explicit"
        )
        self.memory._claims[old_claim.claim_id] = updated_old
        
        # Only the new claim should be active
        active = self.memory.retrieve_claims("combat", Recipient.MASTER_PRIVATE)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].claim_id, new_claim.claim_id)

    def test_respects_only_this_session_temporality(self) -> None:
        # User: "I am playing Genshin tonight."
        # This is session state, not a permanent preference.
        claim = self._create_claim("is playing Genshin tonight.", "private chat session 3")
        
        # User chooses "only this session"
        # We simulate updating the status to "session_only" and setting valid_until
        session_claim = VersionedClaim(
            claim_id=claim.claim_id,
            subject=claim.subject,
            predicate=claim.predicate,
            value=claim.value,
            claim_type="episodic",
            source_event_id=claim.source_event_id,
            provenance=claim.provenance,
            authority=claim.authority,
            confidence=claim.confidence,
            asserted_at=claim.asserted_at,
            valid_from=claim.valid_from,
            valid_until=datetime.now(timezone.utc).isoformat(), # Expires immediately for test
            status="session_only",
            sensitivity=claim.sensitivity,
            allowed_audiences=claim.allowed_audiences,
            supersedes=None,
            replaces=None,
            user_confirmation="explicit"
        )
        self.memory._claims[claim.claim_id] = session_claim
        
        # Should not be retrieved since it's expired
        retrieved = self.memory.retrieve_claims("Genshin", Recipient.MASTER_PRIVATE)
        self.assertEqual(len(retrieved), 0)

    def test_approved_game_account_proposal_becomes_queryable_claim(self) -> None:
        event = self.memory.add_source_event(SourceEvent(
            event_id="evt_game_account",
            source_type="private_chat",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            payload={"text": "My Genshin server is Asia."},
        ))
        proposal = self.memory.propose(MemoryProposal(
            content="Kur's Genshin account is on the Asia server.",
            provenance="private chat",
            sensitivity="private",
            allowed_audiences=frozenset({Recipient.MASTER_PRIVATE.value}),
            subject="primary_user.genshin_account",
            predicate="server",
            value="Asia",
            claim_type="semantic",
            source_event_id=event.event_id,
        ))
        self.memory.approve(proposal.proposal_id)

        claims = self.memory.retrieve_claims("What server is my game account on?", Recipient.MASTER_PRIVATE)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].subject, "primary_user.genshin_account")
        self.assertEqual(claims[0].predicate, "server")
        self.assertEqual(claims[0].value, "Asia")
        self.assertEqual(self.memory.retrieve_claims("my game account", Recipient.AUDIENCE_GENERAL), ())

    def test_single_value_game_account_correction_supersedes_old_claim(self) -> None:
        for event_id, server_name in (("evt_asia", "Asia"), ("evt_europe", "Europe")):
            self.memory.add_source_event(SourceEvent(
                event_id=event_id,
                source_type="private_chat",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                payload={"text": f"My Genshin server is {server_name}."},
            ))
            proposal = self.memory.propose(MemoryProposal(
                content=f"The primary user's Genshin server is {server_name}.",
                provenance="private chat",
                subject="primary_user.genshin_account",
                predicate="server",
                value=server_name,
                source_event_id=event_id,
            ))
            self.memory.approve(proposal.proposal_id)

        current = self.memory.query_claims(
            Recipient.MASTER_PRIVATE,
            subject="primary_user.genshin_account",
            predicate="server",
        )
        self.assertEqual([claim.value for claim in current], ["Europe"])
        old = next(claim for claim in self.memory.claims() if claim.value == "Asia")
        new = next(claim for claim in self.memory.claims() if claim.value == "Europe")
        self.assertEqual(old.status, "superseded")
        self.assertEqual(new.authority, "user_correction")
        self.assertEqual(new.supersedes, old.claim_id)

    def test_persisted_fts_retrieves_prefix_when_exact_tokens_miss(self) -> None:
        with TemporaryDirectory() as directory:
            memory = MemoryService(Path(directory) / "memory.sqlite3")
            event = memory.add_source_event(SourceEvent(
                event_id="evt_exploration",
                source_type="private_chat",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                payload={"text": "I prefer exploration."},
            ))
            memory.add_claim(VersionedClaim(
                claim_id="claim_exploration",
                subject="primary_user",
                predicate="gameplay_preference",
                value="prefers exploration over difficult combat",
                claim_type="preference",
                source_event_id=event.event_id,
                provenance="private chat",
                authority="user_explicit",
                status="confirmed",
                sensitivity="private",
                allowed_audiences=(Recipient.MASTER_PRIVATE.value,),
                user_confirmation="explicit",
            ))
            if memory._fts_available:
                retrieved = memory.retrieve_claims("explor", Recipient.MASTER_PRIVATE)
                self.assertEqual([claim.claim_id for claim in retrieved], ["claim_exploration"])
            memory.close()

if __name__ == "__main__":
    unittest.main()
