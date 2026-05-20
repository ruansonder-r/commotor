class CreateTripLogs < ActiveRecord::Migration[8.1]
  def change
    create_table :trip_logs do |t|
      t.references :carpool_group, null: false, foreign_key: true
      t.integer :recorded_by_user_id
      t.datetime :occurred_at
      t.integer :trip_count

      t.timestamps
    end
  end
end
