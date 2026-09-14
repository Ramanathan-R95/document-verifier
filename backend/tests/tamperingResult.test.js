const TamperingResult = require('../src/models/TamperingResult');

describe('TamperingResult', () => {
  it('accepts structured tampering findings from the AI service', () => {
    const result = new TamperingResult({
      screeningCaseId: '507f1f77bcf86cd799439011',
      findings: [
        {
          type: 'edge_anomaly',
          description: 'Unusual edge patterns detected - possible photo replacement',
          confidence: 0.65,
        },
      ],
    });

    expect(result.validateSync()).toBeUndefined();
    expect(result.findings[0].toObject()).toMatchObject({
      type: 'edge_anomaly',
      description: 'Unusual edge patterns detected - possible photo replacement',
      confidence: 0.65,
    });
  });
});
