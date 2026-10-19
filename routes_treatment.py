from fastapi import APIRouter,Form,HTTPException
from fastapi.responses import Response
from treatment_report import calculate
from web_common import database_connection
from operation_progress import callback
router=APIRouter()

@router.post('/api/treatment-report')
def treatment(host:str=Form('localhost'),port:int=Form(5432),database:str=Form('ecews'),
              username:str=Form('postgres'),password:str=Form(''),schema:str=Form('public'),
              source_table:str=Form('linelist_records'),snapshot_id:str=Form(...),sheet:str=Form(...),
              end_date:str=Form('2026-09-19'),progress_id:str=Form(''),word:bool=Form(False),
              comparison_snapshot_id:str=Form(''),comparison_sheet:str=Form(''),
              activity_start_date:str=Form('2026-07-01'),activity_end_date:str=Form('2026-09-30')):
    notify=lambda event:None
    try:
        notify=callback(progress_id,'report')
        if bool(comparison_snapshot_id)!=bool(comparison_sheet):raise ValueError('Choose a complete quarterly comparison snapshot.')
        if comparison_snapshot_id and schema=='quarterly':raise ValueError('Quarter comparison is selected from the weekly dashboard.')
        from activity_indicators import ActivityCounts
        ActivityCounts(activity_start_date,activity_end_date)
        config=database_connection(host,port,database,username,password)
        comparison=None
        if comparison_snapshot_id:
            comparison=calculate(config,'quarterly','linelist_records',comparison_snapshot_id,comparison_sheet,end_date)
            from periods import quarterly_period
            quarterly_period(comparison['source']['period'])
        report=calculate(config,schema,source_table,snapshot_id,sheet,end_date,progress=notify,activity_start_date=activity_start_date,activity_end_date=activity_end_date,comparison_snapshot_id=comparison_snapshot_id,comparison_sheet=comparison_sheet)
        if comparison:
            report['comparison']=comparison
            from comparison_metrics import compare_group,DEFINITION
            report['comparison_metrics']={
                'all':compare_group(report),'paediatrics':compare_group(report,paediatric=True),
                'states':{name:compare_group(report,name) for name in report['states']},
                'paediatric_states':{name:compare_group(report,name,paediatric=True) for name in report.get('paediatric_states',{})}}
            report['definitions'].append(DEFINITION)
        if schema=='quarterly':report['workflow']='quarterly'
        if word:
            from report_document import build
            return Response(build(report),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                            headers={'Content-Disposition':f'attachment; filename="{'quarterly_' if schema=='quarterly' else ''}treatment_report_{report["end_date"]}.docx"'})
        from report_template import brief_view
        report['brief']=brief_view(report)
        return report
    except ValueError as exc:
        notify(dict(state='failed',phase='failed',error=str(exc)))
        raise HTTPException(400,str(exc)) from None
    except Exception:
        notify(dict(state='failed',phase='failed',error='Could not generate the treatment report'))
        raise HTTPException(400,'Could not generate the report. Check the connection and selected linelist.') from None
