class CreateMemberships < ActiveRecord::Migration[8.1]
  def change
    create_table :memberships do |t|
      t.references :user, null: false, foreign_key: true
      t.references :carpool_group, null: false, foreign_key: true
      t.decimal :cost_split_percentage

      t.timestamps
    end
  end
end
