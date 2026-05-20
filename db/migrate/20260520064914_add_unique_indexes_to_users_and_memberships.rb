class AddUniqueIndexesToUsersAndMemberships < ActiveRecord::Migration[8.1]
  def change
    add_index :users, :uid, unique: true
    add_index :users, :email, unique: true
    add_index :memberships, [ :user_id, :carpool_group_id ], unique: true
  end
end
