WITH approvals_with_min_priority (workflow_id, transition_id, object_id, min_priority) AS
         (
             SELECT workflow_id,
                    transition_id,
                    object_id,
                    MIN(priority) AS min_priority
             FROM {transitionapproval_table}
             WHERE workflow_id = %s
               AND status = %s
             GROUP BY workflow_id, transition_id, object_id
         ),
     authorized_approvals (id, workflow_id, transition_id, source_state_id, object_id, priority) AS
         (
             SELECT ta.id,
                    ta.workflow_id,
                    ta.transition_id,
                    t.source_state_id,
                    ta.object_id,
                    ta.priority
             FROM {transitionapproval_table} ta
                      INNER JOIN {transition_table} t ON t.id = ta.transition_id
                      LEFT JOIN {transitionapproval_permissions_table} tap ON tap.transitionapproval_id = ta.id
                      LEFT JOIN {transitionapproval_groups_table} tag ON tag.transitionapproval_id = ta.id
             WHERE ta.workflow_id = %s
               AND ta.status = %s
               AND (ta.transactioner_id IS NULL OR ta.transactioner_id = %s)
               AND (tap.id IS NULL OR tap.permission_id IN ({permission_placeholders}))
               AND (tag.id IS NULL OR tag.group_id IN ({group_placeholders}))
         ),
     approvals_with_max_priority (id, object_id, source_state_id) AS
         (
             SELECT aa.id, aa.object_id, aa.source_state_id
             FROM approvals_with_min_priority awmp
                      INNER JOIN authorized_approvals aa
                                 ON (
                                         aa.workflow_id = awmp.workflow_id
                                         AND aa.transition_id = awmp.transition_id
                                         AND aa.object_id = awmp.object_id
                                     )
             WHERE awmp.min_priority = aa.priority
         )
SELECT awmp.id
FROM approvals_with_max_priority awmp
         INNER JOIN {workflow_object_table} wot
                    ON (
                            wot.{object_pk_column} = awmp.object_id
                            AND awmp.source_state_id = wot.{state_column}
                        )
