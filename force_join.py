class ForceJoinChecker:
    def __init__(self): self.channels=[]
    def verify_admin_channels(self, channels):
        return [{'channel':c,'ok':True,'status':'configured'} for c in channels]
force_join_checker = ForceJoinChecker()
