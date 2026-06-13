# Delta for plate-detector-ocr

## ADDED Requirements

### Requirement: Plate crop production and boundary event

The system MUST let `PlateDetector` own plate bounding-box selection and crop production from vehicle detections. It MUST publish `PLATE_CROPPED` as the explicit handoff to OCR, and the payload MUST reference the source frame and crop by identifier rather than embedding raw image bytes.

#### Scenario: Successful crop handoff

- GIVEN a vehicle detection with a valid frame reference and a plate region
- WHEN `PlateDetector` processes the detection
- THEN it publishes `PLATE_CROPPED` with track id, vehicle bbox, plate bbox, frame reference, and crop reference
- AND the payload does not contain raw frame or crop bytes

#### Scenario: No plate region found

- GIVEN a vehicle detection with no usable plate region
- WHEN `PlateDetector` processes the detection
- THEN it does not publish `PLATE_CROPPED`
- AND it leaves OCR uninvoked for that detection

### Requirement: OCR backend selection and validation

The system MUST support selecting the OCR backend through configuration. It MUST fail fast when the configured backend is unknown and MUST report the valid backend options in the error.

#### Scenario: Valid backend is selected

- GIVEN a configured OCR backend name that exists
- WHEN the OCR pipeline starts
- THEN it binds that backend successfully

#### Scenario: Unknown backend is rejected

- GIVEN a configured OCR backend name that does not exist
- WHEN the OCR pipeline validates configuration
- THEN it fails with a clear error
- AND the error lists the valid backend options

### Requirement: OCR read normalization and result event

The system MUST consume `PLATE_CROPPED`, run the selected OCR backend, normalize the recognized text, and publish `PLATE_READ` with text, confidence, and error state. Successful reads MUST emit non-empty normalized text.

#### Scenario: OCR success path

- GIVEN a `PLATE_CROPPED` event with a valid crop reference
- WHEN the OCR backend returns readable text
- THEN the text is normalized before publication
- AND `PLATE_READ` includes confidence and a non-error success state

#### Scenario: OCR returns readable text with formatting noise

- GIVEN OCR output that includes spacing or casing noise
- WHEN the result is normalized
- THEN `PLATE_READ` contains the normalized plate text

### Requirement: OCR no-read and failure reporting

The system MUST represent OCR no-read and failure outcomes explicitly. It MUST NOT publish an empty plate text as a silent success.

#### Scenario: OCR no-read

- GIVEN OCR cannot determine a plate text from the crop
- WHEN the OCR result is published
- THEN `PLATE_READ` marks the read as unsuccessful or errored
- AND it does not report empty text as a valid read

#### Scenario: OCR backend failure

- GIVEN the OCR backend fails while processing a crop
- WHEN the failure is handled
- THEN `PLATE_READ` carries an error state or failure reason
- AND no successful plate text is emitted

### Requirement: Event payload scope boundary

The system MUST keep raw frames and crops out of EventBus payload bodies. Event messages MAY reference frame or crop identifiers, but consumers MUST resolve media through stores or adapters.

#### Scenario: Serializable event payloads only

- GIVEN `PLATE_CROPPED` or `PLATE_READ` is published
- WHEN the event is serialized
- THEN the payload contains only references and metadata
- AND it remains safe to transport without embedded image data
