import tempfile,unittest
from pathlib import Path
from activity_indicators import ActivityCounts,MatchIndex

class ActivityTests(unittest.TestCase):
    def test_activity_window_ti_and_status_rules(self):
        counts=ActivityCounts('2026-07-01','2026-09-30',True)
        counts.add(dict(CurrentARTStatus=' Active ',ARTStartDate='2026-07-01',TI='YES',Date_Transfered_In='2026-07-01',Current_Age='10',State='DELTA'),'IIT','matched')
        counts.add(dict(CurrentARTStatus='death',ARTStartDate='2026-09-30',TI=' no ',Outcomes_Date='2026-09-30',Current_Age='30',State='Delta'))
        counts.add(dict(CurrentARTStatus='Discontinued care',Outcomes_Date='2026-07-01',Current_Age='19',State='Delta'))
        counts.add(dict(CurrentARTStatus='Transferred out',Outcomes_Date='2026-09-30T23:59:59',Current_Age='30',State='Delta'))
        counts.add(dict(CurrentARTStatus='Active',ARTStartDate='2026-06-30',Date_Transfered_In='2026-10-01',Outcomes_Date='bad',State='Delta'),' ','matched')
        counts.add(dict(CurrentARTStatus='Active',ARTStartDate='2026-09-30',TI='',Current_Age='20',State='Delta'),'Active','matched')
        counts.add(dict(CurrentARTStatus='Active',ARTStartDate='bad',State='Delta'),None,'unmatched')
        counts.add(dict(CurrentARTStatus='Active',ARTStartDate='2026-10-01',Date_Transfered_In='bad',State='Delta'),None,'ambiguous')
        result=counts.result();self.assertEqual(result['groups']['all'],dict(txnew=2,transferred_in=1,death=1,rtt=1,stopped=1,transferred_out=1,iit=0))
        self.assertEqual(result['groups']['paediatrics']['stopped'],1)
        self.assertEqual(result['groups']['paediatrics']['txnew'],0)
        self.assertEqual(result['groups']['adults']['txnew'],2)
        self.assertEqual(result['quality']['rtt_unmatched_active'],1);self.assertEqual(result['quality']['rtt_ambiguous_active'],1)
        for key in ['art','transfer','outcome']:self.assertEqual(result['quality']['invalid_'+key+'_dates'],1)
    def test_no_previous_snapshot_and_bad_window(self):
        counts=ActivityCounts('2026-07-01','2026-09-30');counts.add({'CurrentARTStatus':'Active'},'IIT','matched')
        self.assertIsNone(counts.result()['groups']['all']['rtt'])
        with self.assertRaises(ValueError):ActivityCounts('2026-10-01','2026-09-30')
    def test_client_matching_fallback_facility_duplicates_and_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            index=MatchIndex(str(Path(folder)/'test.sqlite'))
            try:
                old=dict(Datim_Code='A',PepID='P1',patient_id='1',CurrentARTStatus='IIT')
                current=dict(old,CurrentARTStatus='Active')
                index.add('previous',old,1);index.add('current',current,1)
                self.assertEqual(index.previous(current),('iit','matched'))
                elsewhere=dict(current,Datim_Code='B');index.add('current',elsewhere,2)
                self.assertEqual(index.previous(elsewhere),(None,'unmatched'))
                fallback=dict(current,PepID='NEW');index.add('current',fallback,3)
                # Duplicate current patient_id is ambiguous, even if PepID differs.
                self.assertEqual(index.previous(fallback),(None,'ambiguous'))
                previous2=dict(Datim_Code='A',PepID='P2',patient_id='2',CurrentARTStatus='Active')
                index.add('previous',previous2,2)
                conflict=dict(current,patient_id='2');index.add('current',conflict,4)
                self.assertEqual(index.previous(conflict),(None,'ambiguous'))
            finally:index.close()
        with tempfile.TemporaryDirectory() as folder:
            index=MatchIndex(str(Path(folder)/'test.sqlite'))
            try:
                index.add('previous',old,1)
                changed=dict(old,PepID='CHANGED',CurrentARTStatus='Active');index.add('current',changed,1)
                self.assertEqual(index.previous(changed),('iit','matched'))
                index.add('previous',old,2)
                self.assertEqual(index.previous(changed),(None,'ambiguous'))
            finally:index.close()
    def test_report_cells_and_narrative_use_activity_counts(self):
        from treatment_report import aggregate
        from report_template import table_models,brief_view
        r=aggregate([('Active','180',None,None,None,'10','Delta')],'2026-09-19')
        activity=ActivityCounts('2026-07-01','2026-09-30',True)
        activity.add(dict(CurrentARTStatus='Active',Current_Age=10,State='Delta',ARTStartDate='2026-08-01',TI='NO',Date_Transfered_In='2026-09-01'),'IIT','matched')
        r['activity']=activity.result();tables=table_models(r)
        self.assertEqual(tables[1]['rows'][0][3:6],['1','1','1'])
        self.assertEqual(tables[3]['rows'][0][3:6],['1','1','1'])
        p={p['index']:''.join(t['text'] for t in p['runs']) for p in brief_view(r)['paragraphs']}
        self.assertIn('is 1.',p[6]);self.assertIn('at 1 ',p[13])

    def test_txnew_excludes_yes_with_case_and_spaces(self):
        counts=ActivityCounts('2026-07-01','2026-09-30')
        for ti in ['YES',' Yes ','yes','NO',' no ',None,'']:
            counts.add(dict(ARTStartDate='2026-08-01',TI=ti))
        self.assertEqual(counts.result()['groups']['all']['txnew'],4)

    def test_iit_calculated_dates_statuses_and_quality(self):
        counts=ActivityCounts('2026-07-01','2026-09-30')
        # 3 Aug + 31 refill + 28 = 1 Oct; 19 Aug + 31 + 28 = 17 Oct.
        for pickup,status,refill in [('2026-08-03',' LTFU ',31),('2026-08-19','Lost to follow up',31),('2026-08-02','LTFU',31),('2026-08-20','LTFU',31),('2026-08-03','Active',31),('bad','LTFU',31),('2026-08-03','LTFU',None),('2026-08-03','LTFU',-1),('2026-08-03','LTFU','1.5')]:
            counts.add(dict(Pharmacy_LastPickupdate=pickup,DaysOfARVRefill=refill,CurrentARTStatus=status,Current_Age=15,State='Delta'))
        result=counts.result()
        self.assertEqual(result['groups']['all']['iit'],2)
        self.assertEqual(result['groups']['paediatrics']['iit'],2)
        self.assertEqual(result['states']['Delta']['iit'],2)
        self.assertEqual(result['quality']['iit_missing_or_invalid_inputs'],4)
        with self.assertRaises(ValueError):ActivityCounts('2026-07-01','2026-09-30',iit_start='2026-10-18',iit_end='2026-10-17')

    def test_iit_report_column_and_custom_window(self):
        from treatment_report import aggregate
        from report_template import table_models,brief_view
        counts=ActivityCounts('2026-07-01','2026-09-30',iit_start='2026-10-18',iit_end='2026-10-18')
        counts.add(dict(Pharmacy_LastPickupdate='2026-08-20',DaysOfARVRefill=31,CurrentARTStatus='LTFU',Current_Age=15,State='Delta'))
        r=aggregate([('LTFU',31,None,None,None,15,'Delta')],'2026-10-18');r['activity']=counts.result()
        tables=table_models(r)
        self.assertEqual(tables[1]['rows'][0][6],'1')
        self.assertEqual(tables[3]['rows'][0][6],'1')
        p={p['index']:''.join(run['text'] for run in p['runs']) for p in brief_view(r)['paragraphs']}
        self.assertIn('2026-10-18',p[9]);self.assertIn('1 client',p[16])
