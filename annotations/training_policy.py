"""Validation-only continuation policy; independent of checkpoint selection."""
MINIMUM_EPOCHS=60
MAXIMUM_EPOCHS=200
PATIENCE_EPOCHS=30
SMOOTHING_WINDOW=3
MINIMUM_IMPROVEMENT=0.002

def policy_config():
    return {'minimum_epochs':MINIMUM_EPOCHS,'maximum_epochs':MAXIMUM_EPOCHS,
        'patience_epochs':PATIENCE_EPOCHS,'smoothing_window_epochs':SMOOTHING_WINDOW,
        'minimum_improvement_absolute':MINIMUM_IMPROVEMENT,
        'extension_metric':'mean validation macro recall over the last 3 epochs',
        'checkpoint_metric':'raw validation macro recall; fewer high-confidence errors breaks ties',
        'heldout_used_for_extension':False}

def policy_state(history,epoch):
    anchor=None;last_significant=0;latest_mean=None
    for end in range(SMOOTHING_WINDOW,len(history)+1):
        recent=history[end-SMOOTHING_WINDOW:end]
        latest_mean=sum(row['validation']['macro_recall'] for row in recent)/SMOOTHING_WINDOW
        if anchor is None or latest_mean-anchor>=MINIMUM_IMPROVEMENT-1e-12:
            anchor=latest_mean;last_significant=recent[-1]['epoch']
    if epoch<MINIMUM_EPOCHS:reason='minimum_training'
    elif epoch>=MAXIMUM_EPOCHS:reason='maximum_epochs_reached'
    elif epoch-last_significant>=PATIENCE_EPOCHS:reason='validation_plateau'
    else:reason='waiting_for_significant_improvement'
    return {'epoch':epoch,'smoothed_macro_recall':latest_mean,'significant_macro_recall_anchor':anchor,
        'last_significant_improvement_epoch':last_significant,'epochs_without_significant_improvement':epoch-last_significant,
        'continue_training':reason in ('minimum_training','waiting_for_significant_improvement'),'reason':reason}
