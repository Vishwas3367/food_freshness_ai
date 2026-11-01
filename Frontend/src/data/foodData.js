// Supported reference produce backed by external research datasets.
// Demo placeholder foods without external research datasets (Apple, Mango, Carrot, Broccoli) have been removed.
export const foodItems = [
  {
    id: 1,
    name: 'Banana',
    category: 'Fruit',
    qty: '1.00 kg',
    quantityKg: 1.0,
    days: 4,
    status: 'Fresh',
    score: 82,
    emoji: '🍌',
    color: '#fff3cc',
    note: 'Monitored with temperature, humidity, and VOC sensors from external reference dataset.',
    referenceDataset: 'banana_reference_dataset_code_compatible.csv',
    sensorCoverage: ['Temperature', 'Humidity', 'VOC (TGS2620, TGS2602, SGP40)'],
    sampleCount: 26885,
    referenceConfidence: 0.60,
    isExternalReference: true
  },
  {
    id: 2,
    name: 'Tomato',
    category: 'Vegetable',
    qty: '1.00 kg',
    quantityKg: 1.0,
    days: 5,
    status: 'Fresh',
    score: 85,
    emoji: '🍅',
    color: '#ffe5e1',
    note: 'Monitored with 12-channel MQ gas array and weight-loss tracking from external reference dataset.',
    referenceDataset: 'tomato_reference_dataset_code_compatible.csv',
    sensorCoverage: ['MQ-135 / Array (12 ch)', 'Weight Loss (HX711)', 'Storage Days'],
    sampleCount: 142,
    referenceConfidence: 0.60,
    isExternalReference: true
  }
];

