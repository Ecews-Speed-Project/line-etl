"""Snapshot comparisons use the selected quarterly baseline, independently by cohort."""
def compare_group(report,name='ECEWS',paediatric=False,cohort=None):
    comparison=report.get('comparison')
    cohort=cohort or ('paediatrics' if paediatric else 'all')
    if name=='ECEWS':
        weekly=report['groups'][cohort]
        baseline=comparison['groups'][cohort] if comparison else None
    elif paediatric:
        weekly=report.get('paediatric_states',{}).get(name,{}).get('total')
        baseline=comparison.get('paediatric_states',{}).get(name,{}).get('total') if comparison else None
    else:
        weekly=report.get('states',{}).get(name)
        baseline=comparison.get('states',{}).get(name) if comparison else None
    current=weekly['txcurr'] if weekly is not None else None
    previous=baseline['txcurr'] if baseline is not None else None
    from activity_indicators import activity_group
    events=report.get('activity',{}).get('groups',{}).get(cohort,{}) if name=='ECEWS' else activity_group(report,name,paediatric)
    txnew=events.get('txnew');iit=events.get('iit')
    denominator=previous+txnew if previous is not None and txnew is not None else None
    iit_rate=100*iit/denominator if iit is not None and denominator is not None and denominator>0 else None
    return dict(weekly_txcurr=current,quarter_txcurr=previous,iit_denominator=denominator,
                iit_rate=iit_rate,iit_rate_formatted=rate_text(iit_rate),
                netnew=current-previous if current is not None and previous is not None else None,
                retention_rate=100*current/previous if current is not None and previous is not None and previous>0 else None)


def rate_text(value):return 'N/A' if value is None else f'{value:.1f}%'

DEFINITION='NetNew = weekly TxCurr - selected-quarter TxCurr. CoT/retention = weekly TxCurr / selected-quarter TxCurr x 100. Rates are snapshot ratios, can exceed 100%, and do not track retention of the same clients. Zero or missing quarter denominators are N/A. IIT rate = IIT / (selected-quarter TxCurr + TxNew) x 100, displayed with one decimal place; a zero or missing IIT denominator is N/A.'
