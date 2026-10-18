-- Demo-ready workflow data. Safe to re-run and intentionally uses named natural keys.
WITH wanted(name,latitude,longitude) AS (VALUES
  ('Ward 4 Riverside',12.9716,77.5946),('Ward 9 Hill Colony',12.9820,77.6045),('Ward 2 Canal Side',12.9600,77.5800))
INSERT INTO area(area_type,name,centroid,accuracy_level)
SELECT 'ward',w.name,ST_SetSRID(ST_MakePoint(w.longitude,w.latitude),4326)::geography,'demo'
FROM wanted w
WHERE NOT EXISTS (SELECT 1 FROM area a WHERE a.parent_id IS NULL AND a.area_type='ward' AND a.normalized_name=lower(trim(w.name)));
WITH wanted(name,latitude,longitude) AS (VALUES
  ('Ward 4 Riverside',12.9716,77.5946),('Ward 9 Hill Colony',12.9820,77.6045),('Ward 2 Canal Side',12.9600,77.5800))
UPDATE area a SET centroid=ST_SetSRID(ST_MakePoint(w.longitude,w.latitude),4326)::geography,accuracy_level='demo'
FROM wanted w WHERE a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.parent_id IS NULL AND a2.area_type='ward' AND a2.normalized_name=lower(trim(w.name))) AND a.parent_id IS NULL;

INSERT INTO location(area_id,point,accuracy_level)
SELECT id,centroid,'demo' FROM area a
WHERE a.name IN ('Ward 4 Riverside','Ward 9 Hill Colony','Ward 2 Canal Side')
  AND NOT EXISTS (SELECT 1 FROM location l WHERE l.area_id=a.id AND l.point IS NOT NULL);

INSERT INTO ngo(name,registration_id,ngo_type,state,district,address,capacity,active) VALUES
  ('Seva Sahayata Foundation','MOCK-NGO-001','food relief','Karnataka','Bengaluru Urban','12 Demo Street Bengaluru',120,true),
  ('Udaan Community Care','MOCK-NGO-002','medical support','Karnataka','Bengaluru Urban','45 Sample Road Bengaluru',80,true),
  ('Asha Neighbourhood Trust','MOCK-NGO-003','shelter support','Karnataka','Bengaluru Urban','8 Canal Road Bengaluru',100,true)
ON CONFLICT(registration_id) DO UPDATE SET name=EXCLUDED.name,ngo_type=EXCLUDED.ngo_type,address=EXCLUDED.address,capacity=EXCLUDED.capacity,active=true;

UPDATE ngo n SET location_id=l.id
FROM location l JOIN area a ON a.id=l.area_id
WHERE l.point IS NOT NULL AND a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.name=a.name AND a2.area_type='ward') AND ((n.registration_id='MOCK-NGO-001' AND a.name='Ward 4 Riverside')
  OR (n.registration_id='MOCK-NGO-002' AND a.name='Ward 9 Hill Colony')
  OR (n.registration_id='MOCK-NGO-003' AND a.name='Ward 2 Canal Side'));
UPDATE ngo n SET location_id=(SELECT l.id FROM location l JOIN area a ON a.id=l.area_id WHERE a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.name='Ward 4 Riverside' AND a2.area_type='ward') ORDER BY l.id LIMIT 1)
WHERE n.location_id IS NULL AND n.active;

INSERT INTO resource_type(name,category,unit,perishable) VALUES
  ('Emergency Food Kit','food','kit',true),('First Aid Kit','medical','kit',false),('Blanket','shelter','piece',false)
ON CONFLICT(name) DO UPDATE SET category=EXCLUDED.category,unit=EXCLUDED.unit,perishable=EXCLUDED.perishable;

UPDATE need_type SET resource_type_id=(SELECT id FROM resource_type WHERE name='Emergency Food Kit') WHERE name IN ('food_support','welfare_support');
UPDATE need_type SET resource_type_id=(SELECT id FROM resource_type WHERE name='First Aid Kit') WHERE name='medical_support';
UPDATE need_type SET resource_type_id=(SELECT id FROM resource_type WHERE name='Blanket') WHERE name='wellbeing_visit';

-- Keep inference explainable: one signal should not create every possible need type.
DELETE FROM need_rule WHERE signal_type_id IS NULL;
INSERT INTO need_rule(need_type_id,signal_type_id,threshold,min_signal_count,min_confidence)
SELECT nt.id,st.id,.28,1,.30 FROM (VALUES
  ('food_support','aid_lapse'),('medical_support','health_camp_absence'),
  ('wellbeing_visit','missed_checkin'),('welfare_support','utility_flag')
) x(need_name,signal_name) JOIN need_type nt ON nt.name=x.need_name JOIN signal_type st ON st.name=x.signal_name
ON CONFLICT DO NOTHING;

INSERT INTO resource(resource_type_id,owner_ngo_id,location_id,quantity_total,quantity_available,expires_at,perishable)
SELECT rt.id,n.id,l.id,100,100,now()+interval '400 days',true
FROM resource_type rt JOIN ngo n ON n.registration_id='MOCK-NGO-001' JOIN location l ON l.id=n.location_id
WHERE rt.name='Emergency Food Kit' AND NOT EXISTS (SELECT 1 FROM resource r WHERE r.resource_type_id=rt.id AND r.owner_ngo_id=n.id);
INSERT INTO resource(resource_type_id,owner_ngo_id,location_id,quantity_total,quantity_available,expires_at,perishable)
SELECT rt.id,n.id,l.id,40,40,now()+interval '600 days',false
FROM resource_type rt JOIN ngo n ON n.registration_id='MOCK-NGO-002' JOIN location l ON l.id=n.location_id
WHERE rt.name='First Aid Kit' AND NOT EXISTS (SELECT 1 FROM resource r WHERE r.resource_type_id=rt.id AND r.owner_ngo_id=n.id);
INSERT INTO resource(resource_type_id,owner_ngo_id,location_id,quantity_total,quantity_available,perishable)
SELECT rt.id,n.id,l.id,75,75,false
FROM resource_type rt JOIN ngo n ON n.registration_id='MOCK-NGO-003' JOIN location l ON l.id=n.location_id
WHERE rt.name='Blanket' AND NOT EXISTS (SELECT 1 FROM resource r WHERE r.resource_type_id=rt.id AND r.owner_ngo_id=n.id);

UPDATE resource r SET owner_ngo_id=n.id,location_id=l.id
FROM resource_type rt,ngo n,location l,area a
WHERE r.resource_type_id=rt.id AND r.owner_ngo_id IS NULL
  AND n.registration_id=CASE WHEN rt.category='food' THEN 'MOCK-NGO-001' WHEN rt.category='medical' THEN 'MOCK-NGO-002' ELSE 'MOCK-NGO-003' END
  AND l.id=n.location_id AND a.id=l.area_id;

INSERT INTO volunteer(person_name,pseudonym,home_area_id,location_id,mode,verified,active)
SELECT x.person_name,x.pseudonym,a.id,l.id,x.mode,x.verified,true
FROM (VALUES
  ('Aarav Sharma','mock-volunteer-001','bike',true,'Ward 4 Riverside'),
  ('Meera Iyer','mock-volunteer-002','walk',true,'Ward 9 Hill Colony'),
  ('Kabir Khan','mock-volunteer-003','car',true,'Ward 2 Canal Side')
) x(person_name,pseudonym,mode,verified,area_name)
JOIN area a ON a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.name=x.area_name AND a2.area_type='ward') JOIN LATERAL (SELECT id FROM location WHERE area_id=a.id AND point IS NOT NULL ORDER BY id LIMIT 1) l ON true
ON CONFLICT(pseudonym) DO UPDATE SET person_name=EXCLUDED.person_name,home_area_id=EXCLUDED.home_area_id,location_id=EXCLUDED.location_id,mode=EXCLUDED.mode,verified=EXCLUDED.verified,active=true;
INSERT INTO volunteer_skill(volunteer_id,skill)
SELECT v.id,x.skill FROM (VALUES ('mock-volunteer-001','distribution'),('mock-volunteer-002','first_aid'),('mock-volunteer-003','community_visit')) x(pseudonym,skill)
JOIN volunteer v ON v.pseudonym=x.pseudonym ON CONFLICT DO NOTHING;

INSERT INTO person(pseudonym,display_name,area_id,location_id,household_size,living_alone,active)
SELECT 'demo-live-001','Demo Resident',a.id,l.id,1,true,true
FROM area a JOIN location l ON l.area_id=a.id WHERE a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.name='Ward 4 Riverside' AND a2.area_type='ward')
ON CONFLICT(pseudonym) DO UPDATE SET display_name=EXCLUDED.display_name,area_id=EXCLUDED.area_id,location_id=EXCLUDED.location_id,active=true;
INSERT INTO person_consent(person_id,purpose)
SELECT p.id,'need_inference' FROM person p WHERE p.pseudonym='demo-live-001'
  AND NOT EXISTS (SELECT 1 FROM person_consent pc WHERE pc.person_id=p.id AND pc.purpose='need_inference' AND pc.withdrawn_at IS NULL);
INSERT INTO signal(signal_type_id,person_id,area_id,occurred_at,source,idempotency_key,payload)
SELECT st.id,p.id,p.area_id,now()-interval '2 days','demo','demo-missed-checkin-001','{"demo":true}'::jsonb
FROM signal_type st JOIN person p ON p.pseudonym='demo-live-001'
WHERE st.name='missed_checkin' ON CONFLICT(idempotency_key) DO NOTHING;
SELECT sed_recompute_person(id) FROM person WHERE pseudonym='demo-live-001';

UPDATE need n SET area_id=a.id,location_id=l.id
FROM need_type nt,area a,location l
WHERE n.need_type_id=nt.id AND n.area_id IS NULL
  AND a.id=(SELECT min(a2.id) FROM area a2 WHERE a2.name=CASE WHEN nt.name='medical_support' THEN 'Ward 9 Hill Colony' WHEN nt.name='wellbeing_visit' THEN 'Ward 2 Canal Side' ELSE 'Ward 4 Riverside' END AND a2.area_type='ward')
  AND l.area_id=a.id;
UPDATE need n SET status='rejected',updated_at=now()
FROM need_type nt,person p
WHERE p.pseudonym='demo-live-001' AND nt.id=n.need_type_id AND nt.name IN ('food_support','medical_support','welfare_support')
  AND n.status IN ('suspected','confirmed') AND EXISTS (SELECT 1 FROM need_signal ns JOIN signal s ON s.id=ns.signal_id JOIN signal_type st ON st.id=s.signal_type_id WHERE ns.need_id=n.id AND st.name='missed_checkin');
