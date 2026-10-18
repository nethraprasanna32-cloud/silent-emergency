-- Match custom user-entered resource names by category while preserving exact type links.
CREATE OR REPLACE VIEW sed_candidate_cost AS
 SELECT n.id need_id,v.id volunteer_id,r.id resource_id,
   coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)::numeric distance_m,
   n.priority, coalesce((SELECT count(*) FROM volunteer_skill vs WHERE vs.volunteer_id=v.id AND vs.skill=ANY(nt.required_skills)),0)::numeric skill_hits,
   CASE WHEN r.expires_at IS NULL THEN 0 ELSE greatest(0,1-extract(epoch FROM (r.expires_at-now()))/(30*86400)) END::numeric expiry_urgency,
   coalesce(v.acceptance_rate,0)*coalesce(v.completion_rate,0)::numeric reliability,
   least(1,extract(epoch FROM (now()-coalesce(ns.waiting_since,n.detected_at)))/(30*86400))::numeric starvation,
   coalesce((SELECT served_30d FROM area_service_stat WHERE area_id=n.area_id),0)::numeric zone_service,
   (coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)/1000.0 / nullif((mp.volunteer_speed_kmh->>v.mode)::numeric,0)*60)::numeric eta_minutes,
   (coalesce(ST_Distance(nl.point,vl.point),ST_Distance(na.centroid,va.centroid),100000)<=mp.max_radius_m) in_radius
 FROM need n JOIN need_type nt ON nt.id=n.need_type_id JOIN volunteer v ON v.active
 CROSS JOIN matching_parameters mp
 LEFT JOIN location nl ON nl.id=n.location_id LEFT JOIN area na ON na.id=n.area_id
 LEFT JOIN location vl ON vl.id=v.location_id LEFT JOIN area va ON va.id=v.home_area_id
 LEFT JOIN need_starvation ns ON ns.need_id=n.id
 JOIN resource r ON r.quantity_available>0
 JOIN resource_type rtype ON rtype.id=r.resource_type_id
   AND (r.resource_type_id=nt.resource_type_id OR rtype.category=CASE
     WHEN nt.name IN ('food_support','welfare_support') THEN 'food'
     WHEN nt.name='medical_support' THEN 'medical'
     WHEN nt.name='wellbeing_visit' THEN 'shelter'
     ELSE rtype.category END)
 WHERE n.status IN ('suspected','confirmed');
