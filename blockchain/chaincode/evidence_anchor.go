package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type EvidenceAnchorContract struct {
	contractapi.Contract
}

type EvidenceAnchor struct {
	AnchorID      string  json:"anchor_id"
	CaseID        string  json:"case_id"
	EvidenceID    string  json:"evidence_id"
	SHA256        string  json:"sha256"
	EventType     string  json:"event_type"
	Actor         string  json:"actor"
	Timestamp     string  json:"timestamp"
	Source        string  json:"source"
	MetadataHash  string  json:"metadata_hash"
	TransactionID string  json:"transaction_id"
	BlockNumber   *uint64 json:"block_number,omitempty"
}

func (s *EvidenceAnchorContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	fmt.Println("Drishtik Forensic Evidence Anchor Chaincode Initialized")
	return nil
}

func (s *EvidenceAnchorContract) AnchorEvidence(
	ctx contractapi.TransactionContextInterface,
	anchorID string,
	caseID string,
	evidenceID string,
	sha256 string,
	eventType string,
	actor string,
	timestamp string,
	source string,
	metadataHash string,
) (*EvidenceAnchor, error) {
	if anchorID == "" || caseID == "" || evidenceID == "" || sha256 == "" {
		return nil, fmt.Errorf("anchor_id, case_id, evidence_id, and sha256 are strictly required")
	}

	txID := ctx.GetStub().GetTxID()
	txTimestamp, err := ctx.GetStub().GetTxTimestamp()
	recordTime := timestamp
	if err == nil && txTimestamp != nil {
		recordTime = time.Unix(txTimestamp.Seconds, int64(txTimestamp.Nanos)).UTC().Format(time.RFC3339)
	}

	anchor := EvidenceAnchor{
		AnchorID:      anchorID,
		CaseID:        caseID,
		EvidenceID:    evidenceID,
		SHA256:        sha256,
		EventType:     eventType,
		Actor:         actor,
		Timestamp:     recordTime,
		Source:        source,
		MetadataHash:  metadataHash,
		TransactionID: txID,
		BlockNumber:   nil,
	}

	anchorJSON, err := json.Marshal(anchor)
	if err != nil {
		return nil, fmt.Errorf("failed to serialize evidence anchor: %v", err)
	}

	key := fmt.Sprintf("ANCHOR_%s_%s", caseID, evidenceID)
	err = ctx.GetStub().PutState(key, anchorJSON)
	if err != nil {
		return nil, fmt.Errorf("failed to persist evidence anchor to state: %v", err)
	}

	return &anchor, nil
}

func (s *EvidenceAnchorContract) GetEvidenceAnchor(
	ctx contractapi.TransactionContextInterface,
	caseID string,
	evidenceID string,
) (*EvidenceAnchor, error) {
	key := fmt.Sprintf("ANCHOR_%s_%s", caseID, evidenceID)
	anchorJSON, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, fmt.Errorf("failed to read from ledger: %v", err)
	}
	if anchorJSON == nil {
		return nil, fmt.Errorf("no anchor record found for case %s evidence %s", caseID, evidenceID)
	}

	var anchor EvidenceAnchor
	err = json.Unmarshal(anchorJSON, &anchor)
	if err != nil {
		return nil, fmt.Errorf("failed to deserialize anchor: %v", err)
	}

	return &anchor, nil
}

func (s *EvidenceAnchorContract) VerifyEvidenceHash(
	ctx contractapi.TransactionContextInterface,
	caseID string,
	evidenceID string,
	currentSHA256 string,
) (bool, error) {
	anchor, err := s.GetEvidenceAnchor(ctx, caseID, evidenceID)
	if err != nil {
		return false, err
	}
	return anchor.SHA256 == currentSHA256, nil
}

func (s *EvidenceAnchorContract) GetEvidenceHistory(
	ctx contractapi.TransactionContextInterface,
	caseID string,
	evidenceID string,
) ([]*EvidenceAnchor, error) {
	key := fmt.Sprintf("ANCHOR_%s_%s", caseID, evidenceID)
	resultsIterator, err := ctx.GetStub().GetHistoryForKey(key)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch history for key %s: %v", key, err)
	}
	defer resultsIterator.Close()

	var records []*EvidenceAnchor
	for resultsIterator.HasNext() {
		response, err := resultsIterator.Next()
		if err != nil {
			return nil, err
		}
		var record EvidenceAnchor
		if len(response.Value) > 0 {
			if err := json.Unmarshal(response.Value, &record); err == nil {
				records = append(records, &record)
			}
		}
	}
	return records, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&EvidenceAnchorContract{})
	if err != nil {
		fmt.Printf("Error creating Drishtik EvidenceAnchorContract chaincode: %s", err.Error())
		return
	}
	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting Drishtik EvidenceAnchorContract chaincode: %s", err.Error())
	}
}
