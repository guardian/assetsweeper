#!/usr/bin/suidperl -wT
#This helper script is installed suid-root, to allow permissions to be set without requiring the whole vsingester to be run as root
use File::Basename;

our $only_allow="^/srv"; #only allow files matching this expression to be changed
our $desired_owner=504; #vidispine user on vidispine VMs/transcoder
our $desired_group=696631985;   #ag_multimedia_creator on the client workstations
our $media_permissions=oct(664);
our $dir_permissions=oct(775);
my $filepath;

if($ARGV[0]=~/$only_allow/){
    $ARGV[0]=~/^(.*)$/;
    $filepath=$1;
} else {
    print "-ERROR: File path ".$ARGV[0]." is not allowed (does not match $only_allow)\n";
    exit(1);
}

if(! -f $filepath){
    print "-ERROR: File $filepath does not exist.\n";
    exit(1);
}
chown($desired_owner,$desired_group,$filepath);
chown($desired_owner,$desired_group,dirname($filepath));
chmod($media_permissions,$filepath);
chmod($dir_permissions,dirname($filepath));
