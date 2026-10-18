"""Verify the currently observed and predicted point before native input."""

def verify_latest_click(model, frame, observed, predicted, expected_label, order, minimum_score=.94):
    canonical, top, scale = model.normalize(frame)
    state = model.screen_state.classify(canonical)
    report = {'accepted': False, 'phase': state['phase'], 'order': state['order'],
              'expected_label': expected_label, 'observed_point': list(observed),
              'predicted_point': list(predicted), 'predictions': []}
    if state['phase'] != 'playing' or state['order'] != order:
        report['reason'] = 'game_phase_changed'
        return report
    classifier = model.point_classifier or model.classifier
    if classifier is None:
        report['reason'] = 'point_classifier_unavailable'
        return report
    crops = []
    for point in [observed, predicted]:
        x, y = round(point[0] / scale), round((point[1] - top) / scale)
        if not (350 <= x <= 1190 and 185 <= y <= 720):
            report['reason'] = 'point_left_board'
            return report
        crops.append(canonical[y-32:y+32, x-32:x+32])
    report['minimum_score'] = minimum_score
    report['predictions'] = classifier.classify(crops)
    report['accepted'] = all(prediction['label'] == expected_label and prediction['score'] >= minimum_score
                             for prediction in report['predictions'])
    report['reason'] = 'confirmed' if report['accepted'] else 'food_prediction_changed'
    return report
