CREATE OR REPLACE FUNCTION user_transactions_v3(integer)
RETURNS json AS
$$
WITH transactions AS (

    SELECT users_transaction.id,
           CASE users_transaction.type
               WHEN 1 THEN 'deposit'
               WHEN 2 THEN 'withdrawal'
               ELSE 'unknown'
           END AS type,
           CASE users_transaction.status
               WHEN 1 THEN 'pending'
               WHEN 2 THEN 'completed'
               ELSE 'unknown'
           END AS status,
           CASE WHEN users_transactiondeposit.amount IS NOT NULL THEN users_transactiondeposit.amount
                ELSE users_transaction.amount
           END AS amount,
           CASE WHEN users_transaction.type = 1 THEN DATE_TRUNC('month', date)::DATE
                ELSE date
           END AS date,
           users_transaction.created,
           users_transaction.updated,
           users_transaction.source_id,
           users_transactionsource.name AS source_name,
           users_transactionsource.store_id AS store_id,
           users_transaction.user_id,
           users_transaction.licensed AS transaction_licensed,
           users_transactiondeposit.id AS deposit_id,
           users_transactiondeposit.amount AS deposit_amount,
           users_transactiondeposit.isrc_id AS deposit_isrc_id,
           users_transactiondeposit.transaction_id AS deposit_transaction_id,
           codes_isrc.code AS isrc,
           codes_isrc.licensed AS isrc_licensed,
           releases_song.id AS song_id,
           CASE WHEN releases_song.version = '' OR releases_song.version IS NULL
                THEN CASE WHEN releases_song.explicit = 1
                          THEN CONCAT(releases_song.name, ' - explicit')
                          WHEN releases_song.explicit = 2
                          THEN CONCAT(releases_song.name, ' - clean')
                          ELSE releases_song.name
                     END
                ELSE CASE WHEN releases_song.explicit = 1
                          THEN CONCAT(releases_song.name, ' - ', releases_song.version, ' - explicit')
                          WHEN releases_song.explicit = 2
                          THEN CONCAT(releases_song.name, ' - ', releases_song.version, ' - clean')
                          ELSE CONCAT(releases_song.name, ' - ', releases_song.version)
                     END
           END as song_name,
           RANK() OVER(PARTITION BY codes_isrc.code ORDER BY releases_song.id) AS isrc_sequence,                              
           ROW_NUMBER() OVER(PARTITION BY users_transaction.date, releases_song.id ORDER BY users_transactionsource.store_id) AS monthly_deposit_store_sequence
    FROM users_transaction
        LEFT OUTER JOIN users_transactionsource
        ON users_transaction.source_id = users_transactionsource.id

        LEFT OUTER JOIN users_transactiondeposit
        ON users_transaction.id = users_transactiondeposit.transaction_id
        
        LEFT OUTER JOIN codes_isrc
        ON users_transactiondeposit.isrc_id = codes_isrc.id
        
        LEFT OUTER JOIN releases_song
        ON users_transactiondeposit.isrc_id = releases_song.isrc_id

  WHERE user_id = $1
    AND users_transaction.status IN (1, 2)

), date_track_store AS (

   -- we need to collapse stores that share the same UI id (store_id)
   -- pre-aggregate these with the correct shape

   -- note: display_grouping as as need to apply different grouping rules to deposits and withdrawals

   SELECT user_id,
          status,
          date,
          CASE WHEN type = 'withdrawal' THEN id
               ELSE NULL
          END AS withdrawal_display_grouping,
          type,
          MIN(created) AS created,
          MAX(updated) AS updated,
          MIN(id) AS id,
          SUM(amount) AS amount,
          MIN(deposit_id) AS deposit_id,
          isrc,
          isrc_licensed,
          song_id,
          song_name,
          store_id,
          MIN(monthly_deposit_store_sequence) AS monthly_deposit_store_sequence,
          CASE WHEN store_id IS NOT NULL THEN
                    json_build_object(
                       'id', store_id,
                       'amount', SUM(amount)
                    )
               ELSE NULL
          END AS store_amount
     FROM transactions
    WHERE (type = 'withdrawal' AND transaction_licensed = false) OR (type = 'deposit' AND isrc_sequence = 1)
    GROUP BY
          user_id,
          status,
          date,
          withdrawal_display_grouping,
          type,
          isrc,
          isrc_licensed,
          song_id,
          song_name,
          store_id

), date_track_grouped AS (

   SELECT user_id,
          status,
          type,
          withdrawal_display_grouping,
          date, 
          song_id,
          MIN(created) AS created,
          MAX(updated) AS updated,
          MIN(id) AS id,
          SUM(amount) AS amount,
          json_build_object(
            'id', MAX(deposit_id),
            'isrc', MAX(isrc),
            'amount', SUM(amount),
            'licensed', bool_and(isrc_licensed),
            'song_id', song_id,
            'song_name', MAX(song_name),
            'stores', ARRAY_AGG(store_amount ORDER BY monthly_deposit_store_sequence)
          ) AS deposit
     FROM date_track_store
    GROUP BY
          user_id,
          status,
          type,
          withdrawal_display_grouping,
          date, 
          song_id

), date_grouped AS (

   SELECT user_id,
          date,
          json_build_object(
            'deposits', CASE WHEN type = 'deposit' THEN ARRAY_AGG(deposit ORDER BY song_id) ELSE NULL END,
            'id', MIN(id),
            'user_id', user_id,
            'status', status,
            'type', type,
            'amount', SUM(amount),
            'date', date,
            'created', MIN(created),
            'updated', MAX(updated)
          ) AS period
     FROM date_track_grouped
    GROUP BY
          date,
          type,
          withdrawal_display_grouping,
          status,
          user_id

), summary AS (

   SELECT user_id,
          SUM(CASE WHEN type = 'deposit' THEN amount ELSE 0 END) AS total_deposits,
          SUM(CASE WHEN type = 'deposit' AND isrc_licensed = true THEN amount ELSE 0 END) AS total_licensed_track_deposits,
          SUM(CASE WHEN type = 'deposit' AND isrc_licensed = false THEN amount ELSE 0 END) AS total_unlicensed_track_deposits,
          SUM(CASE WHEN type = 'withdrawal' THEN amount ELSE 0 END) AS total_withdrawals,
          SUM(CASE WHEN type = 'withdrawal' AND transaction_licensed = true THEN amount ELSE 0 END) AS total_licensed_withdrawals,
          SUM(CASE WHEN type = 'withdrawal' AND transaction_licensed = false THEN amount ELSE 0 END) AS total_unlicensed_withdrawals
     FROM transactions
    WHERE (type = 'withdrawal') OR (type = 'deposit' AND isrc_sequence = 1)
    GROUP BY user_id

), grouped AS (

   SELECT user_id,
         ARRAY_AGG(period ORDER BY date) AS transactions
    FROM date_grouped
   GROUP BY user_id

)
SELECT json_build_object(
           'total', summary.total_deposits,
           'balance', (total_unlicensed_track_deposits + total_unlicensed_withdrawals),
           'transactions', grouped.transactions
       )
  FROM summary
       INNER JOIN grouped 
       ON summary.user_id = grouped.user_id
;

$$ LANGUAGE SQL;
