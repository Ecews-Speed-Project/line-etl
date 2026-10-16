"""Snapshot comparisons use the selected quarterly baseline, independently by cohort."""
def compare_group(report,name='ECEWS',paediatric=False):
    comparison=report.get('comparison')
    cohort='paediatrics' if paediatric else 'all'
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
    return dict(weekly_txcurr=current,quarter_txcurr=previous,
                netnew=current-previous if current is not None and previous is not None else None,
                retention_rate=100*current/previous if current is not None and previous is not None and previous>0 else None)


def rate_text(value):return 'N/A' if value is None else f'{value:.1f}%'

DEFINITION='NetNew = weekly TxCurr - selected-quarter TxCurr. CoT/retention = weekly TxCurr / selected-quarter TxCurr x 100. Rates are snapshot ratios, can exceed 100%, and do not track retention of the same clients. Zero or missing quarter denominators are N/A.'
